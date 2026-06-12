# Emby API Reference

## Overview

EmbyD uses the following Emby REST API endpoints. All API calls require authentication via `X-Emby-Token` header unless noted.

## Authentication

### Login
```
POST /Users/AuthenticateByName
Content-Type: application/json

{
    "Username": "user",
    "Pw": "password",
    "Password": "sha1_hex_of_password"
}
```

Response:
```json
{
    "User": {
        "Id": "user_id",
        "Name": "user"
    },
    "AccessToken": "token_string"
}
```

## Media Discovery

### Get User
```
GET /Users
Headers: X-Emby-Token: <token>
```

### Get Views (Libraries)
```
GET /Users/{userId}/Views
Headers: X-Emby-Token: <token>
```

### Search Items
```
GET /Users/{userId}/Items?SearchTerm={query}&IncludeItemTypes=Movie,Episode&Limit=20
Headers: X-Emby-Token: <token>
```

EmbyD searches downloadable media items: movies and TV episodes. Series folders are not treated as direct download targets; download an episode item ID instead.

### Get Item
```
GET /Users/{userId}/Items/{itemId}
Headers: X-Emby-Token: <token>
```

## Playback

### Get PlaybackInfo
```
GET /Items/{itemId}/PlaybackInfo?UserId={userId}
Headers: X-Emby-Token: <token>
```

Response (relevant fields):
```json
{
    "MediaSources": [
        {
            "Id": "media_source_id",
            "Container": "mkv",
            "Path": "/path/to/file.mkv",
            "Protocol": "File",
            "Size": 13421772800,
            "Bitrate": 40000000,
            "SupportsDirectStream": true,
            "SupportsTranscoding": true,
            "RequiresTranscoding": false,
            "IsRemote": false
        }
    ]
}
```

## Download

### Direct File Download
```
GET /Items/{itemId}/Download?ApiKey={token}
Headers: X-Emby-Token: <token>
```
Returns raw file binary stream.

### Direct Stream
```
GET /Videos/{itemId}/stream?Static=true&MediaSourceId={mediaSourceId}&api_key={token}
Headers: X-Emby-Token: <token>
Headers: Range: bytes=0-8191999
```

## Error Responses

| HTTP Code | Meaning | Handling |
|-----------|---------|----------|
| 200 | Success | Proceed |
| 206 | Partial Content | Range request success |
| 401 | Unauthorized | Token invalid, re-login |
| 403 | Forbidden | No download permission |
| 404 | Not Found | Item deleted/unavailable |
| 416 | Range Not Satisfiable | File complete, verify |
| 500 | Server Error | Retry with backoff |
| 502 | Bad Gateway | Retry with backoff |
| 503 | Service Unavailable | Retry with backoff |
