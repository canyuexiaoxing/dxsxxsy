import io
import tempfile
import unittest
from pathlib import Path
from reader.core import MaterialReader, InputError
from reader.vision import VisionResult, VisionClient, VisionError
from reader.config import Settings
from reader.store import MaterialStore
import pymupdf
import httpx
from PIL import Image
from fastapi.testclient import TestClient
from reader.api import create_app


def image_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (200, 100), 'white').save(buffer, 'PNG')
    return buffer.getvalue()


def pdf_bytes(mixed=False):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), 'Recruitment: salary and job duties. ' * 3)
    if mixed:
        page = doc.new_page()
        page.insert_image(page.rect, stream=image_bytes())
    page = doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


class FakeVision:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def extract(self, data, mime):
        self.calls += 1
        if self.fail:
            raise VisionError('视觉接口暂时不可用')
        return VisionResult(text='培训费用19800元', issues=[], unreadable=False)


class ReaderTests(unittest.TestCase):
    def test_text_and_empty(self):
        reader = MaterialReader(FakeVision())
        result = reader.read_text('招聘信息')
        self.assertEqual(result.pages[0].text, '招聘信息')
        self.assertEqual(result.pages[0].page_number, 1)
        with self.assertRaises(InputError):
            reader.read_text('   ')

    def test_text_limit(self):
        with self.assertRaises(InputError):
            MaterialReader(FakeVision()).read_text('a' * 100001)

    def test_mixed_pdf_keeps_blank_page(self):
        vision = FakeVision()
        result = MaterialReader(vision).read_file('contract.pdf', pdf_bytes(True))
        self.assertEqual([p.page_number for p in result.pages], [1, 2, 3])
        self.assertEqual([p.method for p in result.pages], ['pdf_text', 'vision', 'blank'])
        self.assertEqual(vision.calls, 1)
        self.assertIn('salary', result.pages[0].text)

    def test_failed_page_does_not_hide_other_pages(self):
        result = MaterialReader(FakeVision(True)).read_file('contract.pdf', pdf_bytes(True))
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.pages[1].status, 'failed')
        self.assertIn('salary', result.pages[0].text)

    def test_image_and_actual_format(self):
        result = MaterialReader(FakeVision()).read_file('chat.jpg', image_bytes())
        self.assertEqual(result.kind, 'image')
        self.assertEqual(result.pages[0].method, 'vision')
        with self.assertRaises(InputError):
            MaterialReader(FakeVision()).read_file('chat.png', b'not an image')

    def test_limits_and_encrypted_pdf(self):
        doc = pymupdf.open()
        for _ in range(31): doc.new_page()
        with self.assertRaises(InputError):
            MaterialReader(FakeVision()).read_file('long.pdf', doc.tobytes())
        encrypted = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='secret')
        with self.assertRaises(InputError):
            MaterialReader(FakeVision()).read_file('locked.pdf', encrypted)
        doc.close()
        with self.assertRaises(InputError):
            MaterialReader(FakeVision()).read_file('a.png', b'x' * (20*1024*1024+1))

    def test_store_and_filename(self):
        with tempfile.TemporaryDirectory() as root:
            store = MaterialStore(Path(root))
            result = MaterialReader(FakeVision()).read_file('../../chat.png', image_bytes())
            store.save(result, image_bytes())
            self.assertEqual(result.filename, 'chat.png')
            self.assertEqual(store.load(result.material_id).pages[0].text, '培训费用19800元')
            self.assertTrue(store.original_path(result.material_id).is_file())
            with self.assertRaises(InputError): store.load('../escape')


class VisionTests(unittest.TestCase):
    def test_request_and_json_response(self):
        def handler(request):
            self.assertIn(b'image_url', request.content)
            self.assertEqual(request.headers['authorization'], 'Bearer TEST_ONLY')
            return httpx.Response(200, json={'choices':[{'message':{'content':'{"text":"招聘","issues":[],"unreadable":false}'}}]})
        settings = Settings(api_key='TEST_ONLY')
        result = VisionClient(settings, transport=httpx.MockTransport(handler)).extract(image_bytes(), 'image/png')
        self.assertEqual(result.text, '招聘')

    def test_errors_do_not_echo_secrets(self):
        for response in [httpx.Response(401, text='TEST_ONLY'), httpx.Response(200,json={'choices':[{'message':{'content':'bad json TEST_ONLY'}}]})]:
            client = VisionClient(Settings(api_key='TEST_ONLY'), transport=httpx.MockTransport(lambda req: response))
            with self.assertRaises(VisionError) as context: client.extract(image_bytes(), 'image/png')
            self.assertNotIn('TEST_ONLY', str(context.exception))

    def test_missing_key(self):
        with self.assertRaises(VisionError): VisionClient(Settings(api_key='')).extract(image_bytes(), 'image/png')


class ApiTests(unittest.TestCase):
    def test_mixed_upload_and_original_preview(self):
        with tempfile.TemporaryDirectory() as root:
            client = TestClient(create_app(Settings(data_dir=Path(root)), vision=FakeVision()))
            response = client.post('/api/materials', data={'text':'请读取这些资料'}, files=[('files',('contract.pdf',pdf_bytes(),'application/pdf')),('files',('chat.png',image_bytes(),'image/png'))])
            self.assertEqual(response.status_code, 200)
            materials = response.json()['materials']
            self.assertEqual(len(materials), 3)
            mid = materials[-1]['material_id']
            self.assertEqual(client.get('/api/materials/'+mid).status_code, 200)
            self.assertEqual(client.get('/api/materials/'+mid+'/original').content, image_bytes())
            self.assertEqual(client.post('/api/materials').status_code, 400)

    def test_unsupported_file_and_file_count(self):
        with tempfile.TemporaryDirectory() as root:
            client = TestClient(create_app(Settings(data_dir=Path(root)), vision=FakeVision()))
            response = client.post('/api/materials', files={'files':('program.exe',b'bad','application/octet-stream')})
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(response.json()['errors']),1)
            response = client.post('/api/materials', files=[('files',(f'{i}.png',image_bytes(),'image/png')) for i in range(6)])
            self.assertEqual(response.status_code,400)


if __name__ == '__main__': unittest.main()
