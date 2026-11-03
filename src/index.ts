# 1. Inicializar o repositório Git local e garantir a branch main
git init
git branch -M main

# 2. Ligar ao repositório remoto no GitHub (faz isto apenas uma vez)
git remote add origin https://github.com/rootsnake/ClientRO.git

# 3. Adicionar os ficheiros respeitando o .gitignore recém-criado
git add .

# 4. Criar o commit inicial com os ficheiros base
git commit -m "feat: estrutura inicial do cliente e script de conexao"

# 5. Enviar para o repositório remoto definindo a branch upstream
git push -u origin main