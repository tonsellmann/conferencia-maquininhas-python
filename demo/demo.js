// A demonstração: o pacote conferencia/ rodando no navegador pelo Pyodide, sobre o mês de exemplo.
// O relatório é desenhado com as mesmas classes do painel em Django.

const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v314.0.4/full/';
const MODULOS = ['__init__', 'dinheiro', 'formatos', 'taxas', 'casamento', 'depositos', 'relatorio'];
const EXEMPLO = ['caixa-outubro-2026.csv', 'cartix-outubro-2026.csv', 'pagaja-october-2026.csv', 'vendemais-outubro-2026.csv', 'banco-outubro-2026.csv'];
const TAXAS = {
  Cartix: { debito: '1.37', credito: '2.49', 'parcelado 2-6': '3.49', 'parcelado 7-12': '3.99' },
  'PagaJá': { debito: '1.49', credito: '3.15', 'parcelado 2-12': '3.79' },
  Vendemais: { debito: '0.99', credito: '2.69', 'parcelado 2-6': '3.29', 'parcelado 7-12': '3.79' },
};
const NOME_DA_FAIXA = { debito: 'Débito', credito: 'Crédito à vista', 'parcelado 2-6': 'Parcelado 2 a 6x', 'parcelado 7-12': 'Parcelado 7 a 12x', 'parcelado 2-12': 'Parcelado 2 a 12x' };

const $ = (s) => document.querySelector(s);
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const reais = (c) => (c / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const dia = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
const pct = (t) => `${String(t).replace('.', ',')}%`;

let arquivos = {};
let pyodide = null;

function etapa(texto, progresso) {
  const alvo = $('[data-etapa]');
  if (alvo) alvo.textContent = texto;
  const barra = $('[data-progresso]');
  if (barra) barra.style.width = `${progresso}%`;
}

function desenharArquivos(nomes, proprios = false) {
  $('[data-arquivos]').innerHTML = nomes
    .map((nome) => `<li>${proprios ? esc(nome) : `<a href="exemplos/${nome}" download>${esc(nome)}</a>`}<small>${(arquivos[nome].length / 1024).toFixed(0)} KB</small></li>`)
    .join('');
}

function desenharTaxas() {
  const linhas = [];
  for (const [maquininha, faixas] of Object.entries(TAXAS)) {
    linhas.push(`<tr class="maquininha"><td colspan="2">${esc(maquininha)}</td></tr>`);
    for (const [faixa, valor] of Object.entries(faixas)) {
      linhas.push(`<tr><td><label for="t-${maquininha}-${faixa}">${NOME_DA_FAIXA[faixa]}</label></td><td><input id="t-${maquininha}-${faixa}" inputmode="decimal" value="${valor.replace('.', ',')}" data-maquininha="${esc(maquininha)}" data-faixa="${faixa}"></td></tr>`);
    }
  }
  $('[data-taxas]').innerHTML = linhas.join('');
}

function taxasDaTela() {
  const tabela = {};
  for (const input of document.querySelectorAll('[data-faixa]')) {
    const valor = input.value.trim().replace(',', '.');
    if (!/^\d{1,2}(\.\d{1,2})?$/.test(valor)) continue;
    (tabela[input.dataset.maquininha] ??= {})[input.dataset.faixa] = valor;
  }
  return tabela;
}

async function prepararPython() {
  etapa('Carregando o Python no navegador…', 10);
  const { loadPyodide } = await import(`${PYODIDE}pyodide.mjs`);
  pyodide = await loadPyodide({ indexURL: PYODIDE });
  etapa('Carregando o pandas…', 45);
  await pyodide.loadPackage(['pandas']);
  etapa('Carregando a conferência…', 80);
  pyodide.FS.mkdirTree('/home/pyodide/conferencia');
  for (const modulo of MODULOS) {
    const codigo = await (await fetch(`conferencia/${modulo}.py`)).text();
    pyodide.FS.writeFile(`/home/pyodide/conferencia/${modulo}.py`, codigo);
  }
  await pyodide.runPythonAsync('import sys, json\nsys.path.insert(0, "/home/pyodide")\nfrom conferencia import conferir');
}

async function conferirAgora() {
  const inicio = performance.now();
  pyodide.globals.set('arquivos_js', pyodide.toPy(arquivos));
  pyodide.globals.set('taxas_json', JSON.stringify(taxasDaTela()));
  const json = await pyodide.runPythonAsync('json.dumps(conferir({k: bytes(v) for k, v in arquivos_js.items()}, json.loads(taxas_json)))');
  desenharRelatorio(JSON.parse(json), Math.round(performance.now() - inicio));
}

function desenharRelatorio(r, ms) {
  const t = r.totais ?? {};
  const partes = [];
  partes.push(`<h1>${r.periodo ? `Conferência de ${dia(r.periodo.de)} a ${dia(r.periodo.ate)}/${r.periodo.ate.slice(0, 4)}` : 'Conferência'}</h1>`);
  partes.push(`<p class="apoio">${Object.keys(arquivos).length} arquivos · conferido em ${ms} ms, no seu navegador${t.conferido_ate ? ` · banco até ${dia(t.conferido_ate)}` : ''}</p>`);
  if (r.erros?.length) partes.push(`<ul class="erros">${r.erros.map((e) => `<li>${esc(e)}</li>`).join('')}</ul>`);
  if (r.totais && Object.keys(t).length) {
    partes.push(`<div class="numeros">
      <div class="numero"><span>Vendido no cartão</span><strong>${reais(t.bruto)}</strong></div>
      <div class="numero"><span>Taxas pagas</span><strong>${reais(t.taxa)}</strong></div>
      <div class="numero${t.cobrado_a_mais ? ' numero--alerta' : ''}"><span>Cobrado acima do contratado</span><strong>${reais(t.cobrado_a_mais)}</strong></div>
      <div class="numero${t.nao_recebido ? ' numero--alerta' : ''}"><span>Previsto e não recebido</span><strong>${reais(t.nao_recebido)}</strong></div>
    </div>`);
  }
  partes.push('<h2>O que conferir</h2>');
  partes.push(r.alertas.length
    ? `<ul class="alertas">${r.alertas.map((a) => `<li class="alerta alerta--${a.gravidade}"><strong>${esc(a.titulo)}</strong><p>${esc(a.detalhe)}</p></li>`).join('')}</ul>`
    : '<p class="tudo-certo">Tudo bate: taxas, vendas e depósitos.</p>');
  if (r.maquininhas.length) {
    partes.push(`<h2>Por maquininha</h2><div class="rolagem"><table class="tabela"><thead><tr><th>Maquininha</th><th class="n">Vendas</th><th class="n">Bruto</th><th class="n">Taxa paga</th><th class="n">Taxa efetiva</th><th class="n">A mais</th><th class="n">Líquido</th></tr></thead><tbody>${r.maquininhas
      .map((m) => `<tr><td>${esc(m.maquininha)}</td><td class="n">${m.vendas}</td><td class="n">${reais(m.bruto)}</td><td class="n">${reais(m.taxa)}</td><td class="n">${pct(m.taxa_efetiva)}</td><td class="n">${reais(m.cobrado_a_mais)}</td><td class="n">${reais(m.liquido)}</td></tr>`)
      .join('')}</tbody></table></div>`);
  }
  if (r.vendas && r.vendas.no_cartao) {
    const v = r.vendas;
    partes.push(`<h2>Vendas do caixa</h2><p class="apoio">${v.no_cartao} vendas no cartão: ${v.casadas} encontradas no extrato da maquininha (no máximo ${String(v.maior_diferenca_minutos).replace('.', ',')} minutos de diferença), ${v.sem_transacao} sem transação e ${v.sem_venda} ${v.sem_venda === 1 ? 'transação' : 'transações'} sem venda no caixa.</p>`);
  }
  const problemas = r.depositos.filter((d) => d.situacao !== 'ok');
  if (r.depositos.length) {
    partes.push(`<h2>Depósitos</h2><p class="apoio">${r.depositos.length - problemas.length} de ${r.depositos.length} depósitos entraram certos.</p>`);
    if (problemas.length) {
      partes.push(`<div class="rolagem"><table class="tabela"><thead><tr><th>Dia</th><th>Maquininha</th><th class="n">Previsto</th><th class="n">Entrou</th><th>Situação</th></tr></thead><tbody>${problemas
        .map((d) => `<tr><td>${dia(d.data)}</td><td>${esc(d.maquininha)}</td><td class="n">${reais(d.previsto)}</td><td class="n">${reais(d.recebido)}</td><td><span class="situacao ${d.situacao === 'aguardando' ? 'situacao--espera' : 'situacao--ruim'}">${esc(d.situacao)}</span></td></tr>`)
        .join('')}</tbody></table></div>`);
    }
  }
  if (r.agenda.length) {
    const porDia = new Map();
    for (const a of r.agenda) porDia.set(a.data, (porDia.get(a.data) ?? 0) + a.valor);
    partes.push(`<h2>A receber</h2><p class="apoio">${reais(t.a_receber)} nos próximos ${porDia.size} dias de pagamento.</p><div class="rolagem"><table class="tabela"><thead><tr><th>Dia</th><th class="n">Valor</th></tr></thead><tbody>${[...porDia]
      .slice(0, 8)
      .map(([d, v]) => `<tr><td>${dia(d)}</td><td class="n">${reais(v)}</td></tr>`)
      .join('')}</tbody></table></div>`);
  }
  $('[data-relatorio]').innerHTML = partes.join('');
}

async function carregarExemplo() {
  arquivos = {};
  for (const nome of EXEMPLO) arquivos[nome] = new Uint8Array(await (await fetch(`exemplos/${nome}`)).arrayBuffer());
  desenharArquivos(EXEMPLO);
}

let espera;
document.addEventListener('input', (e) => {
  if (!e.target.matches('[data-faixa]') || !pyodide) return;
  clearTimeout(espera);
  espera = setTimeout(conferirAgora, 350);
});

$('[data-proprios]').addEventListener('change', async (e) => {
  const lista = [...e.target.files];
  if (!lista.length || !pyodide) return;
  arquivos = {};
  for (const arquivo of lista) arquivos[arquivo.name] = new Uint8Array(await arquivo.arrayBuffer());
  desenharArquivos(lista.map((a) => a.name), true);
  await conferirAgora();
});

desenharTaxas();
try {
  await Promise.all([carregarExemplo(), prepararPython()]);
  etapa('Conferindo…', 95);
  await conferirAgora();
  document.documentElement.classList.add('pronto');
} catch (erro) {
  console.error(erro);
  $('[data-relatorio]').innerHTML = `<p class="erros">Não deu para carregar o Python no navegador (${esc(erro.message)}). Recarregue a página.</p>`;
}
