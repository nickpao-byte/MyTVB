package com.mytvb.network

import android.util.Base64
import java.security.MessageDigest
import java.security.SecureRandom

object WbiGenerator {

    private var cachedOriginKey: String? = null
    private var cachedMixinKey: String? = null
    private var cachedBRet: String? = null
    private val secureRandom = SecureRandom()

    fun ensureBRet(): String {
        cachedBRet?.let { return it }
        val rand = ByteArray(44)
        secureRandom.nextBytes(rand)
        rand[36] = 0; rand[37] = 73; rand[38] = 69; rand[39] = 78; rand[40] = 68; rand[41] = 0xAE.toByte(); rand[42] = 0x42; rand[43] = 0x60
        val b64 = Base64.encodeToString(rand, Base64.NO_WRAP)
        val result = b64.takeLast(80)
        cachedBRet = result
        return result
    }

    fun getCachedBRet(): String? = cachedBRet

    private val mixinKeyEncTab = intArrayOf(
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
        27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
        37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
        22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
    )

    fun generateWbiParams(
        params: Map<String, String>,
        imgKey: String,
        subKey: String,
        includeDmParams: Boolean = true
    ): Map<String, String> {
        if (imgKey.isBlank() || subKey.isBlank()) {
            return params
        }

        val originKey = imgKey + subKey
        synchronized(this) {
            if (originKey != cachedOriginKey) {
                cachedOriginKey = null
                cachedMixinKey = null
            }
        }
        val mixinKey = getMixinKey(originKey)
        val wts = System.currentTimeMillis() / 1000
        // Bilibili playurl anti-bot fingerprint must be fresh for each signed request.
        // Generate once here and use the exact same values both for w_rid calculation and output.
        val currentDmParams = if (includeDmParams) buildDmParams() else emptyMap()

        val withWts = params.toMutableMap()
        withWts["wts"] = wts.toString()
        if (includeDmParams) {
            withWts.putAll(currentDmParams)
        }

        val sorted = withWts.entries.sortedBy { it.key }
            .associate { it.key to filterValue(it.value) }
        val query = sorted.entries
            .joinToString("&") { (k, v) -> "${percentEncodeUtf8(k)}=${percentEncodeUtf8(v)}" }
        val wRid = md5(query + mixinKey)

        val result = params.toMutableMap()
        result["wts"] = wts.toString()
        result["w_rid"] = wRid
        if (includeDmParams) {
            result.putAll(currentDmParams)
        }
        return result
    }

    private fun getMixinKey(originKey: String): String {
        synchronized(this) {
            if (originKey == cachedOriginKey && cachedMixinKey != null) {
                return cachedMixinKey!!
            }
        }
        val sb = StringBuilder()
        for (i in mixinKeyEncTab.indices) {
            val index = mixinKeyEncTab[i]
            if (index < originKey.length) {
                sb.append(originKey[index])
            }
        }
        val result = sb.toString().take(32)
        synchronized(this) {
            cachedOriginKey = originKey
            cachedMixinKey = result
        }
        return result
    }

    private fun filterValue(v: String): String = v.filterNot { it in "!\'()*" }

    private fun percentEncodeUtf8(s: String): String {
        val bytes = s.toByteArray(Charsets.UTF_8)
        val sb = StringBuilder(bytes.size * 3)
        for (b in bytes) {
            val c = b.toInt() and 0xFF
            val isUnreserved = c in 'a'.code..'z'.code ||
                c in 'A'.code..'Z'.code ||
                c in '0'.code..'9'.code ||
                c == '-'.code || c == '_'.code || c == '.'.code || c == '~'.code
            if (isUnreserved) {
                sb.append(c.toChar())
            } else {
                sb.append('%')
                sb.append("0123456789ABCDEF"[c ushr 4])
                sb.append("0123456789ABCDEF"[c and 0x0F])
            }
        }
        return sb.toString()
    }

    private fun md5(input: String): String {
        val md = MessageDigest.getInstance("MD5")
        val digest = md.digest(input.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    /**
     * Browser-style dm_* fingerprint, aligned with current yt-dlp/Bilibili playurl handling.
     * Values are regenerated per WBI request instead of reusing one static fingerprint forever.
     */
    private fun buildDmParams(): Map<String, String> {
        val (width, height) = randomScreenDimensions()
        val whRnd = secureRandom.nextInt(114)
        val wh0 = 2 * width + 2 * height + 3 * whRnd
        val wh1 = 4 * width - height + whRnd

        val scrollTop = secureRandom.nextInt(101)
        val ofRnd = secureRandom.nextInt(514)
        val of0 = 3 * scrollTop + ofRnd
        val of1 = 4 * scrollTop + 2 * ofRnd

        // Keep compact JSON: Bilibili's current playurl validation is sensitive to this form.
        val dmImgInter = "{\"ds\":[],\"wh\":[$wh0,$wh1,$whRnd],\"of\":[$of0,$of1,$ofRnd]}"

        return mapOf(
            "dm_img_list" to "[]",
            "dm_img_str" to randomPrintableBase64(secureRandom.nextInt(49) + 16),
            "dm_cover_img_str" to randomPrintableBase64(secureRandom.nextInt(97) + 32),
            "dm_img_inter" to dmImgInter
        )
    }

    private fun randomPrintableBase64(length: Int): String {
        val chars = CharArray(length) {
            // Printable ASCII range, mirroring a browser fingerprint's opaque printable payload.
            (secureRandom.nextInt(95) + 32).toChar()
        }
        return Base64.encodeToString(
            String(chars).toByteArray(Charsets.UTF_8),
            Base64.NO_WRAP
        ).trimEnd('=')
    }

    private fun randomScreenDimensions(): Pair<Int, Int> {
        // Weights follow the current yt-dlp Bilibili extractor distribution.
        var pick = secureRandom.nextInt(78)
        val weighted = arrayOf(
            Triple(1920, 1080, 18),
            Triple(1366, 768, 18),
            Triple(1536, 864, 17),
            Triple(1280, 720, 8),
            Triple(2560, 1440, 7),
            Triple(1440, 900, 5),
            Triple(1600, 900, 5)
        )
        for ((width, height, weight) in weighted) {
            if (pick < weight) return width to height
            pick -= weight
        }
        return 1920 to 1080
    }

    fun extractKeyFromUrl(url: String): String {
        val wbiIndex = url.indexOf("wbi/")
        if (wbiIndex == -1) return ""
        val startIndex = wbiIndex + 4
        val endIndex = url.indexOf(".", startIndex)
        return if (endIndex > startIndex) {
            url.substring(startIndex, endIndex)
        } else {
            ""
        }
    }
}
