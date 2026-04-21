param(
    [string]$EnvFile = "python/.env.target.example",
    [string]$OutputDir = "python/.dry-run/target",
    [int]$PaymentCount = 48,
    [int]$WorkerCount = 6,
    [int]$MaxRounds = 8
)

$pythonExe = "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$env:PYTHONPATH = "E:\trade\aimicropay-tron\python\.vendor;E:\trade\aimicropay-tron\python"

& $pythonExe -m ops_tools.target_dry_run `
    --env-file $EnvFile `
    --output-dir $OutputDir `
    --payment-count $PaymentCount `
    --worker-count $WorkerCount `
    --max-rounds $MaxRounds
