# Access Token

## Interface Info
- Source doc: `鑾峰彇Access Token.md`
- Method: `GET`
- URL path: `/api/oauth/v2/token.json`
- Started at: `2026-04-08T10:04:55.7570479+08:00`
- Duration: `223 ms`
- HTTP status: `200`
- OpenAPI code: `0`
- OpenAPI msg: `success`
- requestId: `241e50da-c7bb-499b-96df-9702c29f0fdc`
- ts: `1775613895621`

## Notes
- Sensitive values are masked in the report for safety.

## Query Params
```json
{
    "client_id":  "368181",
    "client_secret":  "9bbc...cce7",
    "grant_type":  "client_credentials"
}
```

## Body
```json
null
```

## Response
```json
{
    "code":  0,
    "msg":  "success",
    "data":  {
                 "access_token":  "b3d71a52-de7f-4c7d-b127-d56f3e0f8b40",
                 "expires_in":  84850421
             },
    "ts":  1775613895621,
    "requestId":  "241e50da-c7bb-499b-96df-9702c29f0fdc"
}
```
