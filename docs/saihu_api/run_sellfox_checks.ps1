param(
    [Parameter(Mandatory = $true)]
    [string]$ClientId,
    [Parameter(Mandatory = $true)]
    [string]$ClientSecret,
    [string]$BaseUrl = 'https://openapi.sellfox.com',
    [int]$PageSize = 10,
    [int]$QpsProbeCount = 3
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-AccessToken {
    param(
        [string]$BaseUrl,
        [string]$ClientId,
        [string]$ClientSecret
    )

    $uri = '{0}/api/oauth/v2/token.json?client_id={1}&client_secret={2}&grant_type=client_credentials' -f `
        $BaseUrl.TrimEnd('/'),
        [uri]::EscapeDataString($ClientId),
        [uri]::EscapeDataString($ClientSecret)

    $response = Invoke-RestMethod -Uri $uri -Method Get
    if ($response.code -ne 0 -or -not $response.data.access_token) {
        throw ('Get token failed: ' + ($response | ConvertTo-Json -Depth 10 -Compress))
    }

    return $response
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

function Read-ErrorResponse {
    param($Exception)

    if (-not $Exception.Response) {
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

function Invoke-SellfoxApi {
    param(
        [string]$BaseUrl,
        [string]$AccessToken,
        [string]$ClientId,
        [string]$ClientSecret,
        [string]$Name,
        [string]$UrlPath,
        [hashtable]$Body
    )

    $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds().ToString()
    $nonce = (Get-Random -Minimum 10000 -Maximum 99999).ToString()
    $sign = Get-Sign -UrlPath $UrlPath -AccessToken $AccessToken -ClientId $ClientId -ClientSecret $ClientSecret -Timestamp $timestamp -Nonce $nonce

    $query = [ordered]@{
        access_token = $AccessToken
        client_id    = $ClientId
        timestamp    = $timestamp
        nonce        = $nonce
        sign         = $sign
    }

    $queryString = ($query.GetEnumerator() | ForEach-Object {
        '{0}={1}' -f [uri]::EscapeDataString($_.Key), [uri]::EscapeDataString([string]$_.Value)
    }) -join '&'

    $uri = '{0}{1}?{2}' -f $BaseUrl.TrimEnd('/'), $UrlPath, $queryString
    $jsonBody = $Body | ConvertTo-Json -Depth 10 -Compress
    $startedAt = Get-Date

    try {
        $response = Invoke-WebRequest -Uri $uri -Method Post -ContentType 'application/json' -Body $jsonBody -UseBasicParsing
        $content = $response.Content
        $parsed = $content | ConvertFrom-Json -ErrorAction Stop
        return [pscustomobject]@{
            name        = $Name
            urlPath     = $UrlPath
            startedAt   = $startedAt.ToString('o')
            durationMs  = [int]((Get-Date) - $startedAt).TotalMilliseconds
            httpStatus  = [int]$response.StatusCode
            ok          = $true
            requestBody = $Body
            result      = $parsed
        }
    }
    catch {
        $raw = Read-ErrorResponse -Exception $_.Exception
        $parsed = $null
        if ($raw) {
            try {
                $parsed = $raw | ConvertFrom-Json -ErrorAction Stop
            }
            catch {
            }
        }

        $statusCode = $null
        if ($_.Exception.Response) {
            try {
                $statusCode = [int]$_.Exception.Response.StatusCode
            }
            catch {
            }
        }

        return [pscustomobject]@{
            name        = $Name
            urlPath     = $UrlPath
            startedAt   = $startedAt.ToString('o')
            durationMs  = [int]((Get-Date) - $startedAt).TotalMilliseconds
            httpStatus  = $statusCode
            ok          = $false
            requestBody = $Body
            result      = if ($parsed) { $parsed } else { $raw }
            error       = $_.Exception.Message
        }
    }
}

function Get-ResultCode {
    param($Response)
    if ($null -eq $Response -or $null -eq $Response.result) {
        return $null
    }
    return $Response.result.code
}

function Get-ResultMsg {
    param($Response)
    if ($null -eq $Response -or $null -eq $Response.result) {
        return $null
    }
    return $Response.result.msg
}

function Get-OrderRows {
    param($OrderListResponse)

    if ($null -eq $OrderListResponse -or $null -eq $OrderListResponse.result) {
        return @()
    }

    $result = $OrderListResponse.result
    if ($null -eq $result.data) {
        return @()
    }

    $data = $result.data
    if ($data -is [string]) {
        return @()
    }

    if ($data.PSObject.Properties.Name -contains 'rows' -and $null -ne $data.rows) {
        return @($data.rows)
    }

    return @()
}

$tokenResponse = Get-AccessToken -BaseUrl $BaseUrl -ClientId $ClientId -ClientSecret $ClientSecret
$accessToken = $tokenResponse.data.access_token

$checks = @()
$checks += Invoke-SellfoxApi -BaseUrl $BaseUrl -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -Name 'warehouse_list' -UrlPath '/api/warehouseManage/warehouseList.json' -Body @{
    pageNo = '1'
    pageSize = [string]$PageSize
}
$checks += Invoke-SellfoxApi -BaseUrl $BaseUrl -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -Name 'warehouse_item_list' -UrlPath '/api/warehouseManage/warehouseItemList.json' -Body @{
    pageNo = '1'
    pageSize = [string]$PageSize
}
$checks += Invoke-SellfoxApi -BaseUrl $BaseUrl -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -Name 'out_records' -UrlPath '/api/warehouseInOut/outRecords.json' -Body @{
    pageNo = '1'
    pageSize = [string]$PageSize
}
$orderList = Invoke-SellfoxApi -BaseUrl $BaseUrl -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -Name 'order_list' -UrlPath '/api/order/pageList.json' -Body @{
    pageNo = '1'
    pageSize = [string]$PageSize
}
$checks += $orderList

$orderListWide = $null

$orderDetail = $null
$postalCode = $null
$postalCodePresent = $false
$sampleOrder = $null

$orderRows = @(Get-OrderRows -OrderListResponse $orderList)

if ($orderRows.Count -eq 0) {
    $orderListWide = Invoke-SellfoxApi -BaseUrl $BaseUrl -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -Name 'order_list_wide_range' -UrlPath '/api/order/pageList.json' -Body @{
        pageNo = '1'
        pageSize = [string]$PageSize
        dateType = 'createDateTime'
        dateStart = '2024-01-01 00:00:00'
        dateEnd = '2026-12-31 23:59:59'
    }
    $checks += $orderListWide
    $orderRows = @(Get-OrderRows -OrderListResponse $orderListWide)
}

if ((Get-ResultCode -Response $orderList) -eq 0 -and $orderRows.Count -gt 0) {
    $sampleOrder = $orderRows | Where-Object { $_.shopId -and $_.amazonOrderId } | Select-Object -First 1
    if ($sampleOrder) {
        $orderDetail = Invoke-SellfoxApi -BaseUrl $BaseUrl -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -Name 'order_detail' -UrlPath '/api/order/detailByOrderId.json' -Body @{
            shopId = [string]$sampleOrder.shopId
            amazonOrderId = [string]$sampleOrder.amazonOrderId
        }
        $checks += $orderDetail

        if ((Get-ResultCode -Response $orderDetail) -eq 0) {
            $detailData = $orderDetail.result.data
            $postalCodePresent = ($detailData.PSObject.Properties.Name -contains 'postalCode')
            $postalCode = $detailData.postalCode
        }
    }
}

$probeTarget = if ((Get-ResultCode -Response $orderList) -eq 0) {
    @{
        name = 'order_list_qps_probe'
        path = '/api/order/pageList.json'
        body = @{
            pageNo = '1'
            pageSize = '1'
        }
    }
}
else {
    @{
        name = 'warehouse_list_qps_probe'
        path = '/api/warehouseManage/warehouseList.json'
        body = @{
            pageNo = '1'
            pageSize = '1'
        }
    }
}

$qpsProbe = @()
for ($i = 1; $i -le $QpsProbeCount; $i++) {
    $qpsProbe += Invoke-SellfoxApi -BaseUrl $BaseUrl -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -Name ('{0}_{1}' -f $probeTarget.name, $i) -UrlPath $probeTarget.path -Body $probeTarget.body
}

Start-Sleep -Milliseconds 1300
$qpsRecovery = Invoke-SellfoxApi -BaseUrl $BaseUrl -AccessToken $accessToken -ClientId $ClientId -ClientSecret $ClientSecret -Name ('{0}_recovery_after_1300ms' -f $probeTarget.name) -UrlPath $probeTarget.path -Body $probeTarget.body

$summary = [pscustomobject]@{
    token = [pscustomobject]@{
        code = $tokenResponse.code
        msg = $tokenResponse.msg
        expiresIn = $tokenResponse.data.expires_in
        accessToken = $accessToken
        requestId = $tokenResponse.requestId
    }
    readonlyChecks = $checks
    orderDetailPostalCode = [pscustomobject]@{
        sampleOrder = if ($sampleOrder) {
            [pscustomobject]@{
                shopId = [string]$sampleOrder.shopId
                amazonOrderId = [string]$sampleOrder.amazonOrderId
            }
        } else {
            $null
        }
        detailCalled = [bool]$orderDetail
        postalCodeFieldPresent = $postalCodePresent
        postalCode = $postalCode
    }
    qpsProbe = [pscustomobject]@{
        endpoint = $probeTarget.path
        count = $QpsProbeCount
        results = $qpsProbe
        recoveryAfter1300ms = $qpsRecovery
    }
    skipped = @(
        'purchase_create skipped because it is a write/create endpoint and would create real purchase data.'
    )
}

$summary | ConvertTo-Json -Depth 12
