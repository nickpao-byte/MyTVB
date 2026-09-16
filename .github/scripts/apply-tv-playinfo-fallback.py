from pathlib import Path

path = Path('app/src/main/java/com/mytvb/feature/player/VideoPlayerPlayInfoGateway.kt')
text = path.read_text(encoding='utf-8')

text = text.replace(
    'import okhttp3.Request\n',
    'import okhttp3.Request\nimport okhttp3.HttpUrl.Companion.toHttpUrl\nimport com.google.gson.Gson\nimport com.mytvb.model.BaseResponse\n'
)

needle = '''class VideoPlayerPlayInfoGateway(\n    private val apiService: ApiService,\n    private val noCookieApiService: ApiService,\n    private val okHttpClient: OkHttpClient,\n    private val cookieManager: CookieManager,\n    private val sessionGateway: NetworkSessionGateway,\n    private val securityGateway: NetworkSecurityGateway,\n    private val logTag: String\n) {\n'''
replacement = needle + '''\n    private val tvPlayInfoClient = OkHttpClient.Builder()\n        .connectTimeout(10, java.util.concurrent.TimeUnit.SECONDS)\n        .readTimeout(15, java.util.concurrent.TimeUnit.SECONDS)\n        .retryOnConnectionFailure(true)\n        .build()\n    private val gson = Gson()\n\n'''
if needle not in text:
    raise SystemExit('class constructor anchor not found')
text = text.replace(needle, replacement, 1)

needle = '''        AppLog.i(\n            logTag,\n            "playback_diag playinfo started cid=$cid qn=$qualityId hasBvid=${resolvedBvid != null}"\n        )\n        val securityStartedAtMs = SystemClock.elapsedRealtime()\n'''
replacement = '''        AppLog.i(\n            logTag,\n            "playback_diag playinfo started cid=$cid qn=$qualityId hasBvid=${resolvedBvid != null}"\n        )\n\n        val tvResult = requestTvPlayInfo(\n            aid = aid,\n            cid = cid,\n            qualityId = qualityId,\n            fnval = fnval,\n            fourk = fourk\n        )\n        if (tvResult != null && hasPlayableMedia(tvResult.data)) {\n            AppLog.i(\n                logTag,\n                "playback_diag playinfo winner=tv_api cid=$cid code=${tvResult.code} qn=$qualityId"\n            )\n            return tvResult\n        }\n\n        val securityStartedAtMs = SystemClock.elapsedRealtime()\n'''
if needle not in text:
    raise SystemExit('UGC request anchor not found')
text = text.replace(needle, replacement, 1)

needle = '''    private suspend fun requestPrimaryPlayInfo(\n'''
helper = '''    private suspend fun requestTvPlayInfo(\n        aid: Long?,\n        cid: Long,\n        qualityId: Int,\n        fnval: Int,\n        fourk: Int\n    ): PlayInfoResult? = withContext(Dispatchers.IO) {\n        val objectId = aid?.takeIf { it > 0L } ?: return@withContext null\n        val url = "https://api.snm0516.aisee.tv/x/tv/playurl".toHttpUrl().newBuilder()\n            .addQueryParameter("object_id", objectId.toString())\n            .addQueryParameter("appkey", "4409e2ce8ffd12b8")\n            .addQueryParameter("build", "106500")\n            .addQueryParameter("cid", cid.toString())\n            .addQueryParameter("device", "android")\n            .addQueryParameter("fnval", fnval.toString())\n            .addQueryParameter("fnver", "0")\n            .addQueryParameter("fourk", fourk.toString())\n            .addQueryParameter("mid", "0")\n            .addQueryParameter("mobi_app", "android_tv_yst")\n            .addQueryParameter("playurl_type", "1")\n            .addQueryParameter("platform", "android")\n            .addQueryParameter("qn", qualityId.toString())\n            .build()\n\n        val request = Request.Builder()\n            .url(url)\n            .header("User-Agent", "Bilibili Freedoooooom/MarkII")\n            .header("Accept", "application/json")\n            .build()\n\n        runCatching {\n            tvPlayInfoClient.newCall(request).execute().use { response ->\n                if (!response.isSuccessful) {\n                    AppLog.w(logTag, "playback_diag tv_playinfo http=${response.code} cid=$cid")\n                    return@use null\n                }\n                val body = response.body?.string().orEmpty()\n                if (body.isBlank()) return@use null\n                val type = com.google.gson.reflect.TypeToken.getParameterized(\n                    BaseResponse::class.java,\n                    PlayInfoModel::class.java\n                ).type\n                val parsed: BaseResponse<PlayInfoModel> = gson.fromJson(body, type)\n                AppLog.i(\n                    logTag,\n                    "playback_diag tv_playinfo code=${parsed.code} cid=$cid playable=${hasPlayableMedia(parsed.data)}"\n                )\n                PlayInfoResult(\n                    code = parsed.code,\n                    message = parsed.message,\n                    data = parsed.data\n                )\n            }\n        }.onFailure { throwable ->\n            AppLog.w(logTag, "playback_diag tv_playinfo failed cid=$cid msg=${throwable.message}")\n        }.getOrNull()\n    }\n\n    private suspend fun requestPrimaryPlayInfo(\n'''
if needle not in text:
    raise SystemExit('requestPrimaryPlayInfo anchor not found')
text = text.replace(needle, helper, 1)

path.write_text(text, encoding='utf-8')
print('Applied TV PlayInfo primary fallback for UGC')
