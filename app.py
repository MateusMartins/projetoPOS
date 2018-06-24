from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime

app = Flask(__name__)

# Configuração do MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'myflaskapp'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

#configuração do mongoDB
client = MongoClient()
db = client['myflaskapp']
collection = db['articles']

# inicialização do MYSQL
mysql = MySQL(app)

# Index
@app.route('/')
def index():
    return render_template('home.html')

# Sobre
@app.route('/about')
def about():
    return render_template('about.html')

# Artigos
@app.route('/articles')
def articles():
    # Listagem de todos os artigos no mongoDB
    result = collection.find()
    # Adiciona os artigos em uma lista
    all_data = list(result)

    # Valida se existe algum artigo cadastrado
    if all_data:
        return render_template('articles.html', articles=all_data)
    else:
        msg = 'Nenhum artigo cadastrado'
        return render_template('articles.html', msg=msg)

#Exibição de artigo
@app.route('/article/<string:id>/')
def article(id):
    # Seleciona o artigo que foi clicado pelo ObjectId(id)
    result = collection.find_one({'_id':ObjectId(id)})
    return render_template('article.html', article=result)

# Regras de validação do formulário de cadastro
class RegisterForm(Form):
    name = StringField('Nome', [validators.Length(min=1, max=50)])
    username = StringField('Usuário', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Senha', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Senhas diferentes')
    ])
    confirm = PasswordField('Confirme sua senha')

# Cadastro de usuário
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        # Encriptografa a senha
        password = sha256_crypt.encrypt(str(form.password.data))

        # Criação do cursor
        cur = mysql.connection.cursor()

        # Inserção do usuário no MySQL
        cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)", (name, email, username, password))

        # Commit no MySQL
        mysql.connection.commit()

        # Encerra a conexão
        cur.close()

        flash('Registrado com sucesso', 'success')

        return redirect(url_for('login'))
    return render_template('register.html', form=form)

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Pega o valor dos campos
        username = request.form['username']
        password_candidate = request.form['password']

        # Criação do cursor
        cur = mysql.connection.cursor()

        # Procura o usuário no MySQL
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        #Valida se encontrou o usuario no MySQL
        if result > 0:
            data = cur.fetchone()
            #Pega a senha do usuário
            password = data['password']

            # Compara as senhas
            if sha256_crypt.verify(password_candidate, password):
                # Cria a sessão para o usuário
                session['logged_in'] = True
                session['username'] = username

                flash('Login efetuado com sucesso!', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Usuário ou senha incorretos'
                return render_template('login.html', error=error)
            # Encerra a conexão
            cur.close()
        else:
            error = 'Usuário ou senha incorretos'
            return render_template('login.html', error=error)

    return render_template('login.html')

# Valida se o usuário está logado
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Não autorizado, efetue login para acessar está página', 'danger')
            return redirect(url_for('login'))
    return wrap

# Sair
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('Sessão encerrada com sucesso! Volte sempre!', 'success')
    return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    # Seleciona todos os artigos no mongoDB
    result = collection.find()
    # Adiciona os objetos encontrados em uma lista
    all_data = list(result)

    # Valida se alista não está vazia
    if all_data:
        return render_template('dashboard.html', articles=all_data)
    else:
        msg = 'Não existem artigos cadastrados'
        return render_template('dashboard.html', msg=msg)

# Controle do formulário do cadastro de artigo
class ArticleForm(Form):
    title = StringField('Título', [validators.Length(min=1, max=200)])
    body = TextAreaField('Corpo do texto', [validators.Length(min=30)])

# Adicionar artigo
@app.route('/add_article', methods=['GET', 'POST'])
@is_logged_in
def add_article():
    form = ArticleForm(request.form)
    if request.method == 'POST' and form.validate():
        
        # Carrega as informações da tela
        title = form.title.data
        body = form.body.data

        # Cria as informações que serão inseridas no mongoDB
        post = {'title': title,'body': body , 'author': session['username'], 'create_date' : datetime.datetime.utcnow()}

        # Faz a inserção no mongoDB
        collection.insert_one(post)

        flash('Artigo criado com sucesso', 'success')

        return redirect(url_for('dashboard'))

    return render_template('add_article.html', form=form)

# Edição de artigo
@app.route('/edit_article/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_article(id):
    # Faz o consulta no mongoDB pelo ObjectId
    result = collection.find_one({'_id':ObjectId(id)})

    # Carrega o formulário para a edição do artigo
    form = ArticleForm(request.form)
    
    # Carrega as informações do documento que está sendo alterado
    form.title.data = result['title']
    form.body.data = result['body']

    if request.method == 'POST' and form.validate():
        #Pega os valores da tela
        title = request.form['title']
        body = request.form['body']
        # Efetua o update no mongoDB
        collection.update_one({'_id':ObjectId(id)}, {'$set': {'title':title,'body':body}})

        flash('Artigo atualizado com sucesso!', 'success')

        return redirect(url_for('dashboard'))
    return render_template('edit_article.html', form=form)

# Exclusão de artigo
@app.route('/delete_article/<string:id>', methods=['POST'])
@is_logged_in
def delete_article(id):
    # Delete no mongoDB utilizando o ObjectId
    collection.remove({'_id':ObjectId(id)})
    flash('Artigo deletado com sucesso', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.secret_key='secret123'
    app.run(debug=True)