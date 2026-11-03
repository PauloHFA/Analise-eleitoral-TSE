// Executa os filtros offline em um DOM mínimo, sem rede ou dependências de navegador.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
class Element {
  constructor() { this.value = ''; this.children = []; this.events = {}; this.textContent = ''; }
  addEventListener(name, fn) { this.events[name] = fn; }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = children; }
}
const nodes = new Map(payload.ids.map(id => [id, new Element()]));
nodes.get('inv-data').textContent = JSON.stringify(payload.data);
const document = { getElementById: id => nodes.get(id) || null, createElement: () => new Element() };
vm.runInNewContext(payload.script, { document }, { timeout: 10000 });
const body = nodes.get('inv-body');
assert.equal(body.children.length, Math.min(50, payload.data.length));
let checked = 0;
function reset() {
  for (const key of ['kind', 'uf', 'pattern', 'comparable', 'level', 'search']) nodes.get('inv-' + key).value = '';
}
for (const [name, index] of [['kind',0], ['uf',1], ['pattern',4], ['comparable',5], ['level',14]]) {
  for (const value of new Set(payload.data.map(row => String(row[index])))) {
    reset();
    const element = nodes.get('inv-' + name);
    element.value = value;
    element.events.change();
    const expected = payload.data.filter(row => String(row[index]) === value).length;
    assert.ok(nodes.get('inv-count').textContent.startsWith(expected + ' registros;'));
    assert.equal(body.children.length, Math.min(50, expected));
    checked++;
  }
}
reset();
nodes.get('inv-search').value = 'NOME QUE NÃO EXISTE 0987654321';
nodes.get('inv-search').events.input();
assert.equal(body.children.length, 0);
reset();
nodes.get('inv-kind').events.change();
if (payload.data.length > 50) {
  nodes.get('inv-next').onclick();
  assert.ok(nodes.get('inv-count').textContent.includes('página 2 de'));
  assert.equal(body.children.length, Math.min(50, payload.data.length - 50));
  nodes.get('inv-prev').onclick();
  assert.ok(nodes.get('inv-count').textContent.includes('página 1 de'));
}
console.log(JSON.stringify({ status: 'filtros e paginação válidos', rows: payload.data.length, combinations: checked }));
