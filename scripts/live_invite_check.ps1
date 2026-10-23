$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000/api/v1"
$stamp = Get-Date -Format "yyyyMMddHHmmss"
$results = @()

function Invoke-Api {
    param($Method, $Path, $Body, $Token)
    $headers = @{ "Content-Type" = "application/json" }
    if ($Token) { $headers["Authorization"] = "Bearer $Token" }
    $uri = "$base$Path"
    $payload = $null
    if ($null -ne $Body) { $payload = ($Body | ConvertTo-Json -Compress) }
    try {
        $resp = Invoke-WebRequest -Method $Method -Uri $uri -Headers $headers -Body $payload -UseBasicParsing
        $json = $null
        if ($resp.Content) {
            try { $json = $resp.Content | ConvertFrom-Json } catch { $json = $resp.Content }
        }
        return [pscustomobject]@{ status = [int]$resp.StatusCode; json = $json; text = $resp.Content }
    } catch {
        $web = $_.Exception.Response
        $code = 0
        $text = $_.Exception.Message
        if ($web) {
            $code = [int]$web.StatusCode
            try {
                $reader = New-Object System.IO.StreamReader($web.GetResponseStream())
                $text = $reader.ReadToEnd()
            } catch {}
        }
        $json = $null
        if ($text) { try { $json = $text | ConvertFrom-Json } catch {} }
        return [pscustomobject]@{ status = $code; json = $json; text = $text }
    }
}

function Record($name, $ok, $detail) {
    $script:results += [pscustomobject]@{ check = $name; ok = [bool]$ok; detail = "$detail" }
    $mark = if ($ok) { "PASS" } else { "FAIL" }
    Write-Host "$mark  $name  $detail"
}

function Unlock($email, $password, $newPassword) {
    $login = Invoke-Api POST "/ops/auth/login" @{ email = $email; password = $password }
    if ($login.status -ne 200 -or -not $login.json.access_token) { return $login }
    if ($login.json.must_change_password) {
        return Invoke-Api POST "/ops/auth/change-password" @{ current_password = $password; new_password = $newPassword } $login.json.access_token
    }
    return $login
}

$admin = $null
foreach ($candidate in @(
    @{ email = "admin@bti.local"; password = "ChangeMeNow!123" },
    @{ email = "admin@bti.local"; password = "SuperLivePass!99" },
    @{ email = "admin@buruujfintech.com"; password = "ChangeMeNow!123" }
)) {
    $try = Unlock $candidate.email $candidate.password "SuperLivePass!99"
    if ($try.json.access_token) {
        $admin = $try
        Record "super-admin-login" $true $candidate.email
        break
    }
}
if (-not $admin) {
    Record "super-admin-login" $false "Could not login Super Admin"
    $results | Format-Table -AutoSize
    exit 1
}
$adminToken = $admin.json.access_token

$inst = Invoke-Api GET "/institutions" $null $adminToken
$institutionId = $inst.json[0].id
Record "list-institutions" ($institutionId -ne $null) $institutionId

$denyOps = Invoke-Api POST "/ops/auth/users" @{
    email = "deny.ops.$stamp@bank.local"
    full_name = "Should Fail Ops"
    role = "institution_ops"
    institution_id = $institutionId
} $adminToken
Record "super-admin-cannot-invite-fi-ops" ($denyOps.status -eq 403) $denyOps.status

$denyAppr = Invoke-Api POST "/ops/auth/users" @{
    email = "deny.appr.$stamp@bank.local"
    full_name = "Should Fail Approver"
    role = "fi_approver"
    institution_id = $institutionId
} $adminToken
Record "super-admin-cannot-invite-fi-approver" ($denyAppr.status -eq 403) $denyAppr.status

$fiEmail = "live.fi.$stamp@bank.local"
$fiCreate = Invoke-Api POST "/ops/auth/users" @{
    email = $fiEmail
    full_name = "Live FI Admin"
    role = "institution_admin"
    institution_id = $institutionId
} $adminToken
Record "super-admin-invites-fi-admin" ($fiCreate.status -eq 201) "$($fiCreate.status) $($fiCreate.json.role)"

$fi = Unlock $fiEmail $fiCreate.json.temporary_password "FiLivePass!22"
Record "fi-admin-login" ($fi.json.access_token -ne $null) $fiEmail
$fiToken = $fi.json.access_token

$denyBti = Invoke-Api POST "/ops/auth/users" @{
    email = "deny.bti.$stamp@bank.local"
    full_name = "Should Fail BTI"
    role = "bti_ops"
} $fiToken
Record "fi-admin-cannot-invite-bti-ops" ($denyBti.status -eq 403) $denyBti.status

$denySa = Invoke-Api POST "/ops/auth/users" @{
    email = "deny.sa.$stamp@bank.local"
    full_name = "Should Fail SA"
    role = "platform_admin"
} $fiToken
Record "fi-admin-cannot-invite-super-admin" ($denySa.status -eq 403) $denySa.status

$opsEmail = "live.ops.$stamp@bank.local"
$opsCreate = Invoke-Api POST "/ops/auth/users" @{
    email = $opsEmail
    full_name = "Live FI Ops"
    role = "institution_ops"
} $fiToken
Record "fi-admin-invites-fi-ops" ($opsCreate.status -eq 201) "$($opsCreate.status) $($opsCreate.json.role)"

$ops = Unlock $opsEmail $opsCreate.json.temporary_password "OpsLivePass!33"
$opsDeny = Invoke-Api POST "/ops/auth/users" @{
    email = "deny.ops2.$stamp@bank.local"
    full_name = "Ops cannot invite"
    role = "institution_ops"
} $ops.json.access_token
Record "fi-ops-cannot-invite" ($opsDeny.status -eq 403) $opsDeny.status

$fiKey = Invoke-Api POST "/institutions/$institutionId/api-keys" @{
    name = "live-fi-key-$stamp"
    role = "api_client"
} $fiToken
Record "fi-admin-cannot-create-api-key" ($fiKey.status -eq 403) $fiKey.status

$saKey = Invoke-Api POST "/institutions/$institutionId/api-keys" @{
    name = "live-sa-key-$stamp"
    role = "api_client"
} $adminToken
Record "super-admin-creates-api-key" ($saKey.status -eq 201 -and $saKey.json.api_key) "$($saKey.status) $($saKey.json.role)"

$failed = @($results | Where-Object { -not $_.ok })
Write-Host ""
Write-Host ("Passed {0}/{1}" -f ($results.Count - $failed.Count), $results.Count)
if ($failed.Count) { exit 1 }
exit 0
