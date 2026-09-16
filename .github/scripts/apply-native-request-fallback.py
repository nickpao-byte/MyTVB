from pathlib import Path

GATEWAY = Path("app/src/main/java/com/mytvb/feature/player/VideoPlayerPlayInfoGateway.kt")
VIEWMODEL = Path("app/src/main/java/com/mytvb/feature/player/VideoPlayerViewModel.kt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


gateway = GATEWAY.read_text(encoding="utf-8")

gateway = replace_once(
    gateway,
    "import okhttp3.OkHttpClient\nimport okhttp3.Request\nimport retrofit2.HttpException\n",
    "import com.google.gson.JsonObject\n"
    "import com.mytvb.core.common.json.GsonHolder\n"
    "import okhttp3.HttpUrl.Companion.toHttpUrl\n"
    "import okhttp3.OkHttpClient\n"
    "import okhttp3.Request\n"
    "import retrofit2.HttpException\n"
    "import java.util.concurrent.TimeUnit\n",
    "gateway imports",
)

gateway = replace_once(
    gateway,
    "    private var lastSuspiciousUaRefreshAtMs: Long = 0L\n\n    data class PlayInfoResult(\n",
    "    private var lastSuspiciousUaRefreshAtMs: Long = 0L\n\n"
    "    // Deliberately separate from NetworkManager: this client has no browser/HeaderInterceptor\n"
    "    // fingerprint. It is used only after an HTTP 412 from the normal web-profile request.\n"
    "    private val nativePlayInfoClient: OkHttpClient by lazy {\n"
    "        OkHttpClient.Builder()\n"
    "            .cookieJar(cookieManager)\n"
    "            .connectTimeout(10, TimeUnit.SECONDS)\n"
    "            .readTimeout(15, TimeUnit.SECONDS)\n"
    "            .retryOnConnectionFailure(true)\n"
    "            .build()\n"
    "    }\n\n"
    "    data class PlayInfoResult(\n",
    "native client property",
)

old_normal = '''        val normalResponse = runCatching {
            apiService.getVideoPlayInfo(
                avid = aid,
                bvid = bvid,
                cid = cid,
                qn = qualityId,
                fnval = fnval,
                fourk = fourk,
                fnver = 0,
                gaiaVtoken = gaiaVtoken?.takeIf { it.isNotBlank() },
                tryLook = tryLook
            )
        }.onFailure { throwable ->
            if (throwable !is CancellationException) {
                AppLog.e(logTag, "requestPlayInfo normal exception: ${throwable.message}", throwable)
            }
        }.getOrNull()

        if (normalResponse != null) {
            return PlayInfoResult(
                code = normalResponse.code,
                message = normalResponse.message,
                data = normalResponse.data
            )
        }
        return null
    }

    private suspend fun requestTryLookPlayInfo(
'''

new_normal = '''        val normalResponse = try {
            apiService.getVideoPlayInfo(
                avid = aid,
                bvid = bvid,
                cid = cid,
                qn = qualityId,
                fnval = fnval,
                fourk = fourk,
                fnver = 0,
                gaiaVtoken = gaiaVtoken?.takeIf { it.isNotBlank() },
                tryLook = tryLook
            )
        } catch (throwable: Throwable) {
            if (throwable is HttpException && throwable.code() == 412) {
                AppLog.w(
                    logTag,
                    "playback_diag http412 source=normal cid=$cid; switching to native minimal request profile"
                )
                return requestNativeNormalPlayInfo(aid, bvid, cid, qualityId, fnval, fourk)
            }
            if (throwable !is CancellationException) {
                AppLog.e(logTag, "requestPlayInfo normal exception: ${throwable.message}", throwable)
            }
            null
        }

        if (normalResponse != null) {
            if (normalResponse.code == -412) {
                val nativeResult = requestNativeNormalPlayInfo(aid, bvid, cid, qualityId, fnval, fourk)
                if (nativeResult != null) return nativeResult
            }
            return PlayInfoResult(
                code = normalResponse.code,
                message = normalResponse.message,
                data = normalResponse.data
            )
        }
        return null
    }

    private suspend fun requestNativeNormalPlayInfo(
        aid: Long?,
        bvid: String?,
        cid: Long,
        qualityId: Int,
        fnval: Int,
        fourk: Int
    ): PlayInfoResult? = withContext(Dispatchers.IO) {
        val urlBuilder = "https://api.bilibili.com/x/player/playurl".toHttpUrl().newBuilder()
            .addQueryParameter("cid", cid.toString())
            .addQueryParameter("qn", qualityId.toString())
            .addQueryParameter("fnver", "0")
            .addQueryParameter("fnval", fnval.toString())
            .addQueryParameter("fourk", fourk.toString())

        if (!bvid.isNullOrBlank()) {
            urlBuilder.addQueryParameter("bvid", bvid)
        } else {
            aid?.takeIf { it > 0L }?.let { urlBuilder.addQueryParameter("avid", it.toString()) }
        }
        cookieManager.getCookieValue("x-bili-gaia-vtoken")
            ?.trim()
            ?.takeIf { it.isNotBlank() }
            ?.let { urlBuilder.addQueryParameter("gaia_vtoken", it) }
        if (!cookieManager.hasSessionCookie()) {
            urlBuilder.addQueryParameter("try_look", "1")
        }

        val referer = when {
            !bvid.isNullOrBlank() -> "https://www.bilibili.com/video/$bvid"
            else -> "https://www.bilibili.com/"
        }
        val request = Request.Builder()
            .url(urlBuilder.build())
            // A real native Android profile: intentionally no Origin, Client Hints or Sec-Fetch headers.
            .header("User-Agent", "Dalvik/2.1.0 (Linux; U; Android 6.0; Android TV)")
            .header("Accept", "application/json, text/plain, */*")
            .header("Referer", referer)
            .build()

        runCatching {
            nativePlayInfoClient.newCall(request).execute().use { response ->
                AppLog.i(
                    logTag,
                    "playback_diag native_playinfo cid=$cid http=${response.code} host=${request.url.host}"
                )
                if (!response.isSuccessful) return@use null
                val body = response.body?.string().orEmpty()
                if (body.isBlank()) return@use null
                val root = GsonHolder.DEFAULT.fromJson(body, JsonObject::class.java)
                val code = root.get("code")?.asInt ?: -1
                val message = root.get("message")?.asString
                    ?: root.get("msg")?.asString
                    ?: ""
                val dataElement = root.get("data")
                val data = if (dataElement != null && !dataElement.isJsonNull) {
                    GsonHolder.DEFAULT.fromJson(dataElement, PlayInfoModel::class.java)
                } else {
                    null
                }
                PlayInfoResult(code = code, message = message, data = data)
            }
        }.onFailure { error ->
            if (error !is CancellationException) {
                AppLog.e(logTag, "native playinfo request failed: ${error.message}", error)
            }
        }.getOrNull()
    }

    private suspend fun requestTryLookPlayInfo(
'''

gateway = replace_once(gateway, old_normal, new_normal, "normal playinfo fallback")
GATEWAY.write_text(gateway, encoding="utf-8")

viewmodel = VIEWMODEL.read_text(encoding="utf-8")
old_interceptor = '''        .addInterceptor { chain ->
            val userAgent = com.mytvb.network.NetworkManager.getCurrentUserAgent()
            val mediaReferer = when {
                (currentEpId ?: 0L) > 0L -> "https://www.bilibili.com/bangumi/play/ep$currentEpId"
                !currentBvid.isNullOrBlank() -> "https://www.bilibili.com/video/$currentBvid"
                else -> "https://www.bilibili.com/"
            }
            val request = chain.request().newBuilder()
                // Media CDN requests previously stayed on a hard-coded Chrome/119 identity.
                // Match the active web identity and the actual video page on every open/retry.
                .header("User-Agent", userAgent)
                .header("Accept", "*/*")
                .header("Accept-Language", com.mytvb.network.NetworkManager.getAcceptLanguage())
                .header("Referer", mediaReferer)
                // Do not synthesize Origin for native CDN byte-range requests. Current browser/
                // downloader paths rely on Referer for CDN anti-hotlink checks.
                .removeHeader("Origin")
                .build()
            chain.proceed(request)
        }
'''
new_interceptor = '''        .addInterceptor { chain ->
            val userAgent = com.mytvb.network.NetworkManager.getCurrentUserAgent()
            val mediaReferer = when {
                (currentEpId ?: 0L) > 0L -> "https://www.bilibili.com/bangumi/play/ep$currentEpId"
                !currentBvid.isNullOrBlank() -> "https://www.bilibili.com/video/$currentBvid"
                else -> "https://www.bilibili.com/"
            }
            val browserRequest = chain.request().newBuilder()
                .header("User-Agent", userAgent)
                .header("Accept", "*/*")
                .header("Accept-Language", com.mytvb.network.NetworkManager.getAcceptLanguage())
                .header("Referer", mediaReferer)
                .removeHeader("Origin")
                .build()
            val browserResponse = chain.proceed(browserRequest)
            if (browserResponse.code != 412) {
                browserResponse
            } else {
                browserResponse.close()
                val nativeRequest = chain.request().newBuilder()
                    // Retry once with a coherent native Android identity rather than browser spoofing.
                    .header("User-Agent", "Dalvik/2.1.0 (Linux; U; Android 6.0; Android TV)")
                    .header("Accept", "*/*")
                    .header("Referer", mediaReferer)
                    .removeHeader("Origin")
                    .removeHeader("Accept-Language")
                    .build()
                AppLog.w(
                    TAG,
                    "playback_diag media_http412 retry=native host=${nativeRequest.url.host}"
                )
                chain.proceed(nativeRequest)
            }
        }
'''
viewmodel = replace_once(viewmodel, old_interceptor, new_interceptor, "media 412 native retry")
VIEWMODEL.write_text(viewmodel, encoding="utf-8")

print("Applied native HTTP 412 fallback to PlayInfo and media CDN requests")
