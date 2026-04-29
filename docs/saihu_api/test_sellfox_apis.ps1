param(
    [string]$BaseUrl = $(if ($env:SELLFOX_BASE_URL) { $env:SELLFOX_BASE_URL } else { 'https://openapi.sellfox.com' }),
    [string]$AccessToken = $env:SELLFOX_ACCESS_TOKEN,
    [string]$ClientId = $(if ($env:SELLFOX_CLIENT_ID) { $env:SELLFOX_CLIENT_ID } else { '1111111' }),
    [string]$ClientSecret = $env:SELLFOX_CLIENT_SECRET,
    [switch]$Compact
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $AccessToken) {
    throw 'SELLFOX_ACCESS_TOKEN is required.'
}
if (-not $ClientSecret) {
    throw 'SELLFOX_CLIENT_SECRET is required.'
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

    try {
        $response = Invoke-WebRequest -Uri $uri -Method Post -ContentType 'application/json' -Body $jsonBody -UseBasicParsing
        $bodyText = $response.Content
        $parsed = $null
        try {
            $parsed = $bodyText | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
        }

        [pscustomobject]@{
            name        = $Name
            urlPath     = $UrlPath
            httpStatus  = [int]$response.StatusCode
            ok          = $true
            requestUri  = $uri
            requestBody = $Body
            response    = if ($parsed) { $parsed } else { $bodyText }
        }
        return
    }
    catch {
        $statusCode = $null
        $responseText = $null
        $exceptionText = $_.Exception.Message

        if ($_.Exception.Response) {
            try {
                $statusCode = [int]$_.Exception.Response.StatusCode
            }
            catch {
            }

            try {
                $reader = [IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
                try {
                    $responseText = $reader.ReadToEnd()
                }
                finally {
                    $reader.Dispose()
                }
            }
            catch {
            }
        }

        [pscustomobject]@{
            name        = $Name
            urlPath     = $UrlPath
            httpStatus  = $statusCode
            ok          = $false
            requestUri  = $uri
            requestBody = $Body
            error       = $exceptionText
            response    = $responseText
        }
    }
}

$tests = @(
    @{
        Name = 'warehouse_list'
        UrlPath = '/api/warehouseManage/warehouseList.json'
        Body = @{
            pageNo = '1'
            pageSize = '10'
        }
    },
    @{
        Name = 'warehouse_item_list'
        UrlPath = '/api/warehouseManage/warehouseItemList.json'
        Body = @{
            pageNo = '1'
            pageSize = '10'
        }
    },
    @{
        Name = 'out_records'
        UrlPath = '/api/warehouseInOut/outRecords.json'
        Body = @{
            pageNo = '1'
            pageSize = '10'
        }
    },
    @{
        Name = 'order_list'
        UrlPath = '/api/order/pageList.json'
        Body = @{
            pageNo = '1'
            pageSize = '10'
        }
    },
    @{
        Name = 'order_detail'
        UrlPath = '/api/order/detailByOrderId.json'
        Body = @{
            shopId = '1'
            amazonOrderId = 'TEST-ORDER-ID'
        }
    },
    @{
        Name = 'purchase_create'
        UrlPath = '/api/purchase/create.json'
        Body = @{
            warehouseId = '1'
            action = '1'
            includeTax = 'false'
            items = @(
                @{
                    commodityId = '1'
                    num = '1'
                }
            )
        }
    }
)

$results = foreach ($test in $tests) {
    Invoke-SellfoxApi -Name $test.Name -UrlPath $test.UrlPath -Body $test.Body
}

if ($Compact) {
    $results | Select-Object name, httpStatus, ok, error | Format-Table -AutoSize
}
else {
    $results | ConvertTo-Json -Depth 10
}
