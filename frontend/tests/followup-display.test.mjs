import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

test('questions precede concise advice and do not appear on ordinary answers',async()=>{
 const server=await createServer({optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true},appType:'custom'});
 try {
  const {Reply}=await server.ssrLoadModule('/src/App.jsx');
  const result={action:'ask',questions:['费用支付给谁？'],message:'先核实再决定付款。',sources:[],report:null};
  const html=renderToStaticMarkup(React.createElement(Reply,{result,session:{},onFill:()=>{}}));
  assert.ok(html.indexOf('费用支付给谁？')<html.indexOf('先核实再决定付款。'));
  assert.ok(html.includes('根据现有信息'));
  const answer=renderToStaticMarkup(React.createElement(Reply,{result:{...result,action:'answer',questions:[]},session:{},onFill:()=>{}}));
  assert.ok(!answer.includes('我需要先确认'));
 } finally {await server.close()}
});
