param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)

$branchName = "feat/update-" + (Get-Date -Format "yyyyMMdd-HHmmss")

Write-Host "[Git Flow] A criar e mudar para a branch: $branchName" -ForegroundColor Cyan
git checkout -b $branchName

Write-Host "[Git Flow] A adicionar todos os ficheiros..." -ForegroundColor Yellow
git add .

Write-Host "[Git Flow] A criar commit..." -ForegroundColor Yellow
git commit -m "$Message"

Write-Host "[Git Flow] A mudar para a branch main..." -ForegroundColor Cyan
git checkout main

Write-Host "[Git Flow] A fazer merge da branch $branchName para a main..." -ForegroundColor Green
git merge $branchName --no-ff -m "Merge branch '$branchName' into main: $Message"

Write-Host "[Git Flow] A enviar alterações para o repositório remoto (git push)..." -ForegroundColor Cyan
git push origin main

Write-Host "[SUCESSO] Alterações validadas, integradas na main e enviadas com sucesso!" -ForegroundColor Green
