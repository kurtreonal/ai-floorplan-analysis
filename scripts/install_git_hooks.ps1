$ErrorActionPreference = "Stop"

$repositoryRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repositoryRoot)) {
    throw "Run this script from inside the repository."
}

git -C $repositoryRoot config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
    throw "Unable to configure the repository hook path."
}

Write-Output "Repository hooks enabled from .githooks."
