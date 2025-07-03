from flask import Flask, request, redirect, render_template_string, send_file
import barcode
from barcode.writer import ImageWriter
import sqlite3
import pandas as pd
from io import BytesIO
import os

app = Flask(__name__)
conn = sqlite3.connect('estoque.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS produtos (
    codigo TEXT PRIMARY KEY,
    nome TEXT,
    quantidade INTEGER
)
''')
conn.commit()

def gerar_codigo_unico():
    cursor.execute("SELECT COUNT(*) FROM produtos")
    total = cursor.fetchone()[0]
    return f"P{total + 1:05d}"

def gerar_codigo_barras(codigo):
    os.makedirs("codigos", exist_ok=True)
    code128 = barcode.get('code128', codigo, writer=ImageWriter())
    code128.save(f'codigos/{codigo}')

@app.route("/")
def index():
    return redirect("/cadastro")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"]
        quantidade = int(request.form["quantidade"])
        codigo = gerar_codigo_unico()
        gerar_codigo_barras(codigo)
        cursor.execute("INSERT INTO produtos VALUES (?, ?, ?)", (codigo, nome, quantidade))
        conn.commit()
        return render_template_string(confirmacao_html(nome, codigo, quantidade))

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cadastro</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="container py-4">
        <h2 class="mb-4">📋 Cadastro de Produto</h2>
        <form method="POST" class="row g-3">
            <div class="col-md-6">
                <label class="form-label">Nome:</label>
                <input type="text" name="nome" class="form-control" required>
            </div>
            <div class="col-md-6">
                <label class="form-label">Quantidade:</label>
                <input type="number" name="quantidade" class="form-control" required>
            </div>
            <div class="col-12">
                <button type="submit" class="btn btn-primary">Cadastrar</button>
            </div>
        </form>
        <hr>
        <p>
            <a href="/relatorio" class="btn btn-outline-info me-2">📊 Ver Relatório</a>
            <a href="/scanner" class="btn btn-outline-success">📲 Escanear Produto</a>
            <a href="/baixa" class="btn btn-outline-danger">📦 Registrar Saída</a>
        </p>
    </body>
    </html>
    """
    return render_template_string(html)

def confirmacao_html(nome, codigo, quantidade):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Confirmação</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="container py-4">
        <h2>✅ Produto Cadastrado</h2>
        <ul class="list-group mb-3">
            <li class="list-group-item"><strong>Nome:</strong> {nome}</li>
            <li class="list-group-item"><strong>Código gerado:</strong> {codigo}</li>
            <li class="list-group-item"><strong>Quantidade:</strong> {quantidade}</li>
            <li class="list-group-item"><strong>Imagem:</strong> codigos/{codigo}.png</li>
        </ul>
        <a href="/cadastro" class="btn btn-outline-primary me-2">← Cadastrar outro</a>
        <a href="/relatorio" class="btn btn-outline-info">📊 Ver Relatório</a>
    </body>
    </html>
    """

@app.route("/relatorio")
def relatorio():
    termo = request.args.get("busca", "").strip()
    if termo:
        cursor.execute("SELECT codigo, nome, quantidade FROM produtos WHERE nome LIKE ? OR codigo LIKE ?", (f"%{termo}%", f"%{termo}%"))
    else:
        cursor.execute("SELECT codigo, nome, quantidade FROM produtos")
    
    produtos = cursor.fetchall()
    linhas = "".join(f"<tr><td>{codigo}</td><td>{nome}</td><td>{quantidade}</td></tr>" for codigo, nome, quantidade in produtos)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Relatório</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="container py-4">
        <h2>📊 Relatório de Estoque</h2>
        <form method="GET" class="row g-3 mb-4">
            <div class="col-md-6">
                <input type="text" name="busca" class="form-control" placeholder="🔍 Buscar por nome ou código" value="{termo}">
            </div>
            <div class="col-md-6">
                <button type="submit" class="btn btn-outline-primary">Buscar</button>
                <a href="/relatorio" class="btn btn-link">Limpar</a>
            </div>
        </form>
        <table class="table table-striped">
            <thead><tr><th>Código</th><th>Nome</th><th>Quantidade</th></tr></thead>
            <tbody>{linhas}</tbody>
        </table>
        <p>
            <a href="/export/csv" class="btn btn-outline-secondary me-2">⬇️ Exportar CSV</a>
            <a href="/export/xlsx" class="btn btn-outline-secondary">⬇️ Exportar XLSX</a>
        </p>
        <a href="/cadastro" class="btn btn-link">← Voltar ao cadastro</a>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/baixa", methods=["GET", "POST"])
def baixa():
    mensagem = ""
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        cursor.execute("SELECT nome, quantidade FROM produtos WHERE codigo = ?", (codigo,))
        resultado = cursor.fetchone()
        if resultado:
            nome, quantidade = resultado
            if quantidade > 0:
                nova_qtd = quantidade - 1
                cursor.execute("UPDATE produtos SET quantidade = ? WHERE codigo = ?", (nova_qtd, codigo))
                conn.commit()
                mensagem = f"🟢 Baixa realizada: {nome} agora tem {nova_qtd} unidades."
            else:
                mensagem = f"⚠️ Estoque zerado: {nome} não possui unidades disponíveis."
        else:
            mensagem = "❌ Produto não encontrado."

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Baixa de Estoque</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="container py-4">
        <h2>📦 Registrar Saída de Produto</h2>
        <form method="POST" class="row g-3">
            <div class="col-md-6">
                <label class="form-label">Código do produto:</label>
                <input type="text" name="codigo" class="form-control" required>
            </div>
            <div class="col-md-6 align-self-end">
                <button type="submit" class="btn btn-danger">Registrar Baixa</button>
            </div>
        </form>
        <div class="mt-4 fw-bold">{mensagem}</div>
        <hr>
        <a href="/cadastro" class="btn btn-outline-primary me-2">← Voltar ao Cadastro</a>
        <a href="/relatorio" class="btn btn-outline-secondary">📊 Ver Relatório</a>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/scanner", methods=["GET", "POST"])
def scanner():
    mensagem = ""
    operacao = "entrada"

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        operacao = request.form.get("operacao", "entrada")

        cursor.execute("SELECT nome, quantidade FROM produtos WHERE codigo = ?", (codigo,))
        resultado = cursor.fetchone()
        if resultado:
            nome, quantidade = resultado
            if operacao == "entrada":
                nova = quantidade + 1
                mensagem = f"📥 Entrada registrada: {nome} → {nova}"
            elif operacao == "saida":
                if quantidade > 0:
                    nova = quantidade - 1
                    mensagem = f"📤 Saída registrada: {nome} → {nova}"
                else:
                    nova = quantidade
                    mensagem = f"⚠️ Estoque zerado: {nome} não pode ter saída."
            cursor.execute("UPDATE produtos SET quantidade = ? WHERE codigo = ?", (nova, codigo))
            conn.commit()
        else:
            mensagem = f"❌ Produto com código {codigo} não encontrado."

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Escaneamento com Câmera</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/quagga/0.12.1/quagga.min.js"></script>
    </head>
    <body class="container py-4 text-center">
        <h2>📲 Escaneamento com Câmera</h2>
        <form id="operacao-form" class="mb-3">
            <div class="btn-group" role="group">
                <input type="radio" class="btn-check" name="operacao" id="entrada" value="entrada" autocomplete="off" checked>
                <label class="btn btn-outline-success" for="entrada">Entrada</label>

                <input type="radio" class="btn-check" name="operacao" id="saida" value="saida" autocomplete="off">
                <label class="btn btn-outline-danger" for="saida">Saída</label>
            </div>
        </form>
        <video id="preview" class="border mb-3" style="width:100%; max-width:400px;"></video>
        <p id="msg" class="fw-bold">{mensagem}</p>

        <script>
        let operacaoAtual = "entrada";

        document.querySelectorAll("input[name='operacao']").forEach(el => {{
            el.addEventListener("change", () => {{
                operacaoAtual = document.querySelector("input[name='operacao']:checked").value;
            }});
        }});

        function iniciarScanner() {{
            Quagga.init({{
                inputStream: {{
                    name: "Live",
                    type: "LiveStream",
                    target: document.querySelector('#preview'),
                    constraints: {{ facingMode: "environment" }}
                }},
                decoder: {{ readers: ["code_128_reader"] }}
            }}, function(err) {{
                if (err) {{
                    document.getElementById("msg").innerText = "Erro ao acessar a câmera: " + err;
                    return;
                }}
                Quagga.start();
            }});

            Quagga.onDetected(function(data) {{
                let codigo = data.codeResult.code;
                Quagga.stop();

                fetch("/scanner", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/x-www-form-urlencoded" }},
                    body: "codigo=" + codigo + "&operacao=" + operacaoAtual
                }}).then(res => res.text()).then(html => {{
                    document.open();
                    document.write(html);
                    document.close();
                }});
            }});
        }}

        iniciarScanner();
        </script>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/export/csv")
def export_csv():
    cursor.execute("SELECT codigo, nome, quantidade FROM produtos")
    df = pd.DataFrame(cursor.fetchall(), columns=["Código", "Nome", "Quantidade"])
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(output, mimetype="text/csv", download_name="estoque.csv", as_attachment=True)

@app.route("/export/xlsx")
def export_xlsx():
    cursor.execute("SELECT codigo, nome, quantidade FROM produtos")
    df = pd.DataFrame(cursor.fetchall(), columns=["Código", "Nome", "Quantidade"])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Estoque")
    output.seek(0)
    return send_file(output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        download_name="estoque.xlsx", as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
