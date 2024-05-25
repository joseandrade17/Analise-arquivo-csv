import os
import pandas as pd
from flask import Flask, request, render_template, redirect, url_for, Blueprint
from werkzeug.utils import secure_filename
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objs as go
from pandas.errors import ParserError

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xlsm', 'xlsb', 'xltx', 'xltm', 'xls', 'xml', 'xlm', 'xlam', 'xla', 'xlw', 'xlr'}

server = Flask(__name__)
server.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@server.route('/')
def index():
    return render_template('index.html')

@server.route('/upload', methods=['POST', 'GET'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(server.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('dashboard.show_dashboard', filename=filename))
    return render_template('upload.html')

def ler_arquivo(filepath):
    extension = filepath.rsplit('.', 1)[1].lower()
    if extension == 'csv':
        try:
            return pd.read_csv(filepath)
        except ParserError:
            return None
    else:
        return pd.read_excel(filepath)

def analisar_produtos(filepath):
    df = ler_arquivo(filepath)

    if df is None:
        raise ValueError("Erro ao ler o arquivo: problema ao analisar o arquivo CSV ou Excel.")

    colunas_analisadas = [
        'Nome do Produto', 'Nome do Produto Anúncio', 'Localização / Palavra-Chave', 'Impressão', 'Cliques', 'CTR', 'Conversões',
        'Conversões Diretas', 'Taxa de Conversão', 'Taxa de Conversão Direta', 'VBM', 'Receita direta',
        'Despesas', 'ROAS', 'ROAS Direto', 'ACOS', 'ACOS Direto'
    ]

    if 'Nome do Produto' not in df.columns:
        raise KeyError("A coluna 'Nome do Produto' não está presente no arquivo.")

    metricas_por_produto = {}

    for index, row in df.iterrows():
        produto = row['Nome do Produto']

        if produto not in metricas_por_produto:
            metricas_por_produto[produto] = {}

        for coluna in colunas_analisadas:
            if coluna != 'Nome do Produto' and coluna in df.columns:
                valor = row[coluna]
                if isinstance(valor, str) and '%' in valor:
                    valor = float(valor.replace('%', ''))
                metricas_por_produto[produto][coluna] = valor

    return metricas_por_produto

# Integrando Dash com Flask
app_dash = Dash(__name__, server=server, url_base_pathname='/dashboard/')

app_dash.layout = html.Div([
    html.H1("Dashboard de Análise de Produtos", style={'textAlign': 'center', 'marginBottom': '20px'}),
    dcc.Location(id='url', refresh=False),
    dcc.Dropdown(id='produto-dropdown', placeholder="Selecione um produto"),
    html.Div(id='metricas-container'),
    dcc.Graph(id='grafico-metricas')
], style={'maxWidth': '800px', 'margin': 'auto'})

# Estado global para armazenar métricas por produto
metricas_por_produto = {}

@app_dash.callback(
    Output('produto-dropdown', 'options'),
    Input('url', 'search')
)
def atualizar_dropdown(search):
    if search:
        filename = search.split('=')[1]
        filepath = os.path.join(server.config['UPLOAD_FOLDER'], filename)
        try:
            global metricas_por_produto
            metricas_por_produto = analisar_produtos(filepath)
            return [{'label': produto, 'value': produto} for produto in metricas_por_produto.keys()]
        except KeyError as e:
            return [{'label': f"Erro: {str(e)}", 'value': 'error'}]
        except ValueError as e:
            return [{'label': f"Erro: {str(e)}", 'value': 'error'}]
    return []

@app_dash.callback(
    Output('metricas-container', 'children'),
    Input('produto-dropdown', 'value')
)
def atualizar_metricas(produto_selecionado):
    if produto_selecionado and produto_selecionado != 'error':
        metricas = metricas_por_produto.get(produto_selecionado, {})
        metricas_html = [html.H3("Métricas do Produto: " + produto_selecionado, style={'marginTop': '30px'})]
        for metrica, valor in metricas.items():
            metricas_html.append(html.P(f"{metrica}: {valor}"))
        return metricas_html
    return []

@app_dash.callback(
    Output('grafico-metricas', 'figure'),
    Input('produto-dropdown', 'value')
)
def atualizar_grafico(produto_selecionado):
    if produto_selecionado and produto_selecionado != 'error':
        metricas = metricas_por_produto.get(produto_selecionado, {})
        metricas.pop('ROAS', None)
        metricas.pop('ROAS Direto', None)
        metricas.pop('ACOS', None)
        metricas.pop('ACOS Direto', None)
        
        metricas_labels = list(metricas.keys())
        metricas_values = list(metricas.values())

        figura = go.Figure(data=[go.Bar(x=metricas_labels, y=metricas_values)])
        figura.update_layout(title=f'Métricas para o produto: {produto_selecionado}',
                             xaxis_title='Métricas',
                             yaxis_title='Valores')
        return figura
    return go.Figure()

# Blueprint para o Dash
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
def show_dashboard():
    return app_dash.index()

server.register_blueprint(dashboard_bp)

if __name__ == '__main__':
    server.run(debug=True)
