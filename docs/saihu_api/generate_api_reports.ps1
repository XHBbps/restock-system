param(
    [Parameter(Mandatory = $true)]
    [string]$ClientId,
    [Parameter(Mandatory = $true)]
    [string]$ClientSecret,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$BaseUrl = 'https://openapi.sellfox.com'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Mask-Secret {
    param([string]$Value)
    if ([string]::IsNullOrEmpty($Value)) {
        return $Value
    }
    if ($Value.Length -le 8) {
        return ('*' * $Value.Length)
    }
    return ('{0}...{1}' -f $Value.Substring(0, 4), $Value.Substring($Value.Length - 4))
}

function Get-JsonText {
    param($Value)
    if ($null -eq $Value) {
        return 'null'
    }
    return ($Value | ConvertTo-Json -Depth 40)
}

function Read-ErrorResponse {
    param($Exception)

    if (-not ($Exception.PSObject.Properties.Name -contains 'Response') -or -not $Exception.Response) {
        return $null
    }

    $reader = [IO.StreamReader]::new($Exception.Response.GetResponseStream())
    try {
        return $reader.ReadToEnd()
    }
    finally {
        $reader.Dispose()
    }
}

function Get-AccessTokenCall {
    param(
        [string]$BaseUrl,
        [string]$ClientId,
        [string]$ClientSecret
    )

    $uri = '{0}/api/oauth/v2/token.json?client_id={1}&client_secret={2}&grant_type=client_credentials' -f `
        $BaseUrl.TrimEnd('/'),
        [uri]::EscapeDataString($ClientId),
        [uri]::EscapeDataString($ClientSecret)

    $startedAt = Get-Date
    try {
        $response = Invoke-WebRequest -Uri $uri -Method Get -UseBasicParsing
        $parsed = $response.Content | ConvertFrom-Json
        return [pscustomobject]@{
            slug        = 'access-token'
            title       = 'Access Token'
            sourceDoc   = '获取Access Token.md'
            method      = 'GET'
            urlPath     = '/api/oauth/v2/token.json'
            startedAt   = $startedAt.ToString('o')
            durationMs  = [int]((Get-Date) - $startedAt).TotalMilliseconds
            httpStatus  = [int]$response.StatusCode
            queryParams = [ordered]@{
                client_id     = $ClientId
                client_secret = $ClientSecret
                grant_type    = 'client_credentials'
            }
            body        = $null
            result      = $parsed
            notes       = @(
                'Sensitive values are masked in the report for safety.'
            )
        }
    }
    catch {
        $raw = Read-ErrorResponse -Exception $_.Exception
        $parsed = $null
        if ($raw) {
            try {
                $parsed = $raw | ConvertFrom-Json
            }
            catch {
            }
        }

        return [pscustomobject]@{
            slug        = 'access-token'
            title       = 'Access Token'
            sourceDoc   = '获取Access Token.md'
            method      = 'GET'
            urlPath     = '/api/oauth/v2/token.json'
            startedAt   = $startedAt.ToString('o')
            durationMs  = [int]((Get-Date) - $startedAt).TotalMilliseconds
            httpStatus  = if (($_.Exception.PSObject.Properties.Name -contains 'Response') -and $_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { $null }
            queryParams = [ordered]@{
                client_id     = $ClientId
                client_secret = $ClientSecret
                grant_type    = 'client_credentials'
            }
            body        = $null
            result      = if ($parsed) { $parsed } else { $raw }
            error       = $_.Exception.Message
            notes       = @(
                'Sensitive values are masked in the report for safety.'
            )
        }
    }
}

function Get-Sign {
    param(
        [string]$UrlPath,
        [string]$AccessToken,
        [string]$ClientId,
        [string]$ClientSecret,
        [string]$Timestamp,
        [string]$Nonce
    )

    $params = [ordered]@{
        access_token = $AccessToken
        client_id    = $ClientId
        method       = 'post'
        nonce        = $Nonce
        timestamp    = $Timestamp
        url          = $UrlPath
    }

    $payload = ($params.GetEnumerator() | Sort-Object Name | ForEach-Object {
        '{0}={1}' -f $_.Key, $_.Value
    }) -join '&'

    $hmac = [System.Security.Cryptography.HMACSHA256]::new([Text.Encoding]::UTF8.GetBytes($ClientSecret))
    try {
        $hash = $hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($payload))
        return ([System.BitConverter]::ToString($hash)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $hmac.Dispose()
    }
}

function Invoke-SellfoxApi {
    param(
        [string]$Slug,
        [string]$Title,
        [string]$SourceDoc,
        [string]$UrlPath,
        [hashtable]$Body,
        [string[]]$Notes,
        [string]$AccessToken,
        [string]$ClientId,
        [string]$ClientSecret,
        [string]$BaseUrl
    )

    $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds().ToString()
    $nonce = (Get-Random -Minimum 10000 -Maximum 99999).ToString()
    $sign = Get-Sign -UrlPath $UrlPath -AccessToken $AccessToken -ClientId $ClientId -ClientSecret $ClientSecret -Timestamp $timestamp -Nonce $nonce

    $queryParams = [ordered]@{
        access_token = $AccessToken
        client_id    = $ClientId
        timestamp    = $timestamp
        nonce        = $nonce
        sign         = $sign
    }

    $queryString = ($queryParams.GetEnumerator() | ForEach-Object {
        '{0}={1}' -f [uri]::EscapeDataString($_.Key), [uri]::EscapeDataString([string]$_.Value)
    }) -join '&'

    $uri = '{0}{1}?{2}' -f $BaseUrl.TrimEnd('/'), $UrlPath, $queryString
    $bodyJson = $Body | ConvertTo-Json -Depth 20 -Compress
    $startedAt = Get-Date

    try {
        $response = Invoke-WebRequest -Uri $uri -Method Post -ContentType 'application/json' -Body $bodyJson -UseBasicParsing
        $parsed = $response.Content | ConvertFrom-Json
        return [pscustomobject]@{
            slug        = $Slug
            title       = $Title
            sourceDoc   = $SourceDoc
            method      = 'POST'
            urlPath     = $UrlPath
            startedAt   = $startedAt.ToString('o')
            durationMs  = [int]((Get-Date) - $startedAt).TotalMilliseconds
            httpStatus  = [int]$response.StatusCode
            queryParams = $queryParams
            body        = $Body
            result      = $parsed
            notes       = $Notes
        }
    }
    catch {
        $raw = Read-ErrorResponse -Exception $_.Exception
        $parsed = $null
        if ($raw) {
            try {
                $parsed = $raw | ConvertFrom-Json
            }
            catch {
            }
        }

        return [pscustomobject]@{
            slug        = $Slug
            title       = $Title
            sourceDoc   = $SourceDoc
            method      = 'POST'
            urlPath     = $UrlPath
            startedAt   = $startedAt.ToString('o')
            durationMs  = [int]((Get-Date) - $startedAt).TotalMilliseconds
            httpStatus  = if (($_.Exception.PSObject.Properties.Name -contains 'Response') -and $_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { $null }
            queryParams = $queryParams
            body        = $Body
            result      = if ($parsed) { $parsed } else { $raw }
            error       = $_.Exception.Message
            notes       = $Notes
        }
    }
}

function Get-ResultRows {
    param($Entry)

    if ($null -eq $Entry -or $null -eq $Entry.result -or $null -eq $Entry.result.data) {
        return @()
    }
    if ($Entry.result.data.PSObject.Properties.Name -contains 'rows' -and $null -ne $Entry.result.data.rows) {
        return @($Entry.result.data.rows)
    }
    return @()
}

function Get-MaskedQueryParams {
    param($QueryParams)

    $masked = [ordered]@{}
    foreach ($item in $QueryParams.GetEnumerator()) {
        if ($item.Key -in @('client_secret', 'access_token', 'sign')) {
            $masked[$item.Key] = Mask-Secret -Value ([string]$item.Value)
        }
        else {
            $masked[$item.Key] = $item.Value
        }
    }
    return $masked
}

function Write-ReportFile {
    param(
        [string]$Path,
        $Entry
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $maskedQuery = Get-MaskedQueryParams -QueryParams $Entry.queryParams

    $lines.Add('# ' + $Entry.title)
    $lines.Add('')
    $lines.Add('## Interface Info')
    $lines.Add('- Source doc: `' + $Entry.sourceDoc + '`')
    $lines.Add('- Method: `' + $Entry.method + '`')
    $lines.Add('- URL path: `' + $Entry.urlPath + '`')
    $lines.Add('- Started at: `' + $Entry.startedAt + '`')
    $lines.Add('- Duration: `' + [string]$Entry.durationMs + ' ms`')
    $lines.Add('- HTTP status: `' + [string]$Entry.httpStatus + '`')

    if ($Entry.PSObject.Properties.Name -contains 'error' -and $Entry.error) {
        $lines.Add('- Error: `' + $Entry.error + '`')
    }
    if ($Entry.result -and $Entry.result.PSObject.Properties.Name -contains 'code') {
        $lines.Add('- OpenAPI code: `' + [string]$Entry.result.code + '`')
    }
    if ($Entry.result -and $Entry.result.PSObject.Properties.Name -contains 'msg') {
        $lines.Add('- OpenAPI msg: `' + [string]$Entry.result.msg + '`')
    }
    if ($Entry.result -and $Entry.result.PSObject.Properties.Name -contains 'requestId') {
        $lines.Add('- requestId: `' + [string]$Entry.result.requestId + '`')
    }
    if ($Entry.result -and $Entry.result.PSObject.Properties.Name -contains 'ts') {
        $lines.Add('- ts: `' + [string]$Entry.result.ts + '`')
    }

    if ($Entry.notes -and $Entry.notes.Count -gt 0) {
        $lines.Add('')
        $lines.Add('## Notes')
        foreach ($note in $Entry.notes) {
            $lines.Add('- ' + $note)
        }
    }

    $lines.Add('')
    $lines.Add('## Query Params')
    $lines.Add('```json')
    $lines.Add((Get-JsonText -Value $maskedQuery))
    $lines.Add('```')
    $lines.Add('')
    $lines.Add('## Body')
    $lines.Add('```json')
    $lines.Add((Get-JsonText -Value $Entry.body))
    $lines.Add('```')
    $lines.Add('')
    $lines.Add('## Response')
    $lines.Add('```json')
    $lines.Add((Get-JsonText -Value $Entry.result))
    $lines.Add('```')

    Set-Content -LiteralPath $Path -Value ($lines -join [Environment]::NewLine) -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$entries = @()

$tokenCall = Get-AccessTokenCall -BaseUrl $BaseUrl -ClientId $ClientId -ClientSecret $ClientSecret
$entries += $tokenCall

if (-not $tokenCall.result -or $tokenCall.result.code -ne 0 -or -not $tokenCall.result.data.access_token) {
    throw 'Failed to get access_token. Report generation stopped.'
}

$accessToken = [string]$tokenCall.result.data.access_token

$entries += Invoke-SellfoxApi -Slug 'warehouse-list' -Title 'Warehouse List' -SourceDoc '查询仓库列表.md' -UrlPath '/api/warehouseManage/warehouseList.json' -Body @{
    pageNo = '1'
    pageSize = '2'
} -Notes @(
    'pageSize=2 is used to keep the report readable.'
) -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -BaseUrl $BaseUrl

Start-Sleep -Milliseconds 1400
$entries += Invoke-SellfoxApi -Slug 'warehouse-item-list' -Title 'Warehouse Item List' -SourceDoc '查询库存明细.md' -UrlPath '/api/warehouseManage/warehouseItemList.json' -Body @{
    pageNo = '1'
    pageSize = '2'
} -Notes @(
    'pageSize=2 is used to keep the report readable.'
) -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -BaseUrl $BaseUrl

Start-Sleep -Milliseconds 1400
$entries += Invoke-SellfoxApi -Slug 'out-records' -Title 'Out Records' -SourceDoc '其他出库列表页.md' -UrlPath '/api/warehouseInOut/outRecords.json' -Body @{
    pageNo = '1'
    pageSize = '2'
} -Notes @(
    'pageSize=2 is used to keep the report readable.'
) -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -BaseUrl $BaseUrl

Start-Sleep -Milliseconds 1400
$orderList = Invoke-SellfoxApi -Slug 'order-list' -Title 'Order List' -SourceDoc '订单列表.md' -UrlPath '/api/order/pageList.json' -Body @{
    pageNo = '1'
    pageSize = '5'
    dateType = 'createDateTime'
    dateStart = '2024-01-01 00:00:00'
    dateEnd = '2026-12-31 23:59:59'
} -Notes @(
    'A wide createDateTime range is used because the default request without date filters returned data=null for this account.',
    'Earlier sequential tests showed that this endpoint hits code 40019 when called again within about 1 second, so 1 QPS is the safe working assumption.'
) -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -BaseUrl $BaseUrl
$entries += $orderList

$sampleOrder = $null
$orderDetailEntry = $null
$orderRows = @(Get-ResultRows -Entry $orderList)
if ($orderRows.Count -gt 0) {
    $candidates = @($orderRows | Where-Object { $_.shopId -and $_.amazonOrderId } | Select-Object -First 5)
    foreach ($candidate in $candidates) {
        Start-Sleep -Milliseconds 1400
        $candidateDetail = Invoke-SellfoxApi -Slug 'order-detail' -Title 'Order Detail' -SourceDoc '订单详情.md' -UrlPath '/api/order/detailByOrderId.json' -Body @{
            shopId = [string]$candidate.shopId
            amazonOrderId = [string]$candidate.amazonOrderId
        } -Notes @(
            ('Sample order selected from order-list response: shopId=' + [string]$candidate.shopId + ', amazonOrderId=' + [string]$candidate.amazonOrderId),
            'This call is used to verify whether postalCode is returned in real data.'
        ) -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -BaseUrl $BaseUrl

        if (-not $orderDetailEntry) {
            $orderDetailEntry = $candidateDetail
            $sampleOrder = $candidate
        }

        if ($candidateDetail.result -and $candidateDetail.result.code -eq 0 -and $candidateDetail.result.data) {
            $hasPostalCode = ($candidateDetail.result.data.PSObject.Properties.Name -contains 'postalCode') -and `
                -not [string]::IsNullOrEmpty([string]$candidateDetail.result.data.postalCode)
            if ($hasPostalCode) {
                $orderDetailEntry = $candidateDetail
                $sampleOrder = $candidate
                break
            }
        }
    }
}

if ($orderDetailEntry) {
    if ($orderDetailEntry.result -and $orderDetailEntry.result.code -eq 0 -and $orderDetailEntry.result.data) {
        $postalCodeValue = [string]$orderDetailEntry.result.data.postalCode
        if ([string]::IsNullOrEmpty($postalCodeValue)) {
            $orderDetailEntry.notes += 'postalCode field exists in the response, but the selected sample returned null or empty.'
        }
        else {
            $orderDetailEntry.notes += ('postalCode returned in this sample: ' + $postalCodeValue)
        }
    }
    $entries += $orderDetailEntry
}

Start-Sleep -Milliseconds 1400
$entries += Invoke-SellfoxApi -Slug 'purchase-create' -Title 'Purchase Create' -SourceDoc '采购单创建.md' -UrlPath '/api/purchase/create.json' -Body @{
    warehouseId = '-1'
    action = '1'
    includeTax = 'false'
    items = @(
        @{
            commodityId = '-1'
            num = '1'
        }
    )
} -Notes @(
    'Invalid warehouseId and commodityId are intentionally used to avoid creating real purchase data.',
    'This report documents the real API behavior for that invalid-input call.'
) -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -BaseUrl $BaseUrl

$index = New-Object System.Collections.Generic.List[string]
$index.Add('# API Test Reports')
$index.Add('')
$index.Add('- Generated at: `' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz') + '`')
$index.Add('- Base URL: `' + $BaseUrl + '`')
$index.Add('- client_id: `' + $ClientId + '`')
$index.Add('- Note: `client_secret`, `access_token`, and `sign` are masked in these reports.')
$index.Add('')
$index.Add('## Files')

$counter = 1
foreach ($entry in $entries) {
    $fileName = ('{0:D2}-{1}.md' -f $counter, $entry.slug)
    Write-ReportFile -Path (Join-Path $OutputDir $fileName) -Entry $entry
    $index.Add('- [' + $fileName + '](' + $fileName + ')')
    $counter++
}

Set-Content -LiteralPath (Join-Path $OutputDir 'README.md') -Value ($index -join [Environment]::NewLine) -Encoding UTF8
