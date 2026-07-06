package click.jordanbarnes.airtype

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class WebSocketClient(
    private val onConnected: () -> Unit,
    private val onDisconnected: () -> Unit,
    private val onReconnecting: (attempt: Int) -> Unit,
    private val onError: (String) -> Unit
) {
    companion object {
        private const val TAG = "AirType.WebSocket"
        private const val RECONNECT_BASE_DELAY_MS = 3_000L
        private const val RECONNECT_MAX_DELAY_MS = 60_000L
        private const val CLOSE_CODE_AUTH_FAILED = 4401
    }

    @Volatile
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS) // No timeout for WebSocket
        .build()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private var reconnectJob: Job? = null
    @Volatile
    private var isUserDisconnected = false
    @Volatile
    private var lastServerIp = ""
    @Volatile
    private var lastPort = 0
    @Volatile
    private var lastToken = ""
    @Volatile
    private var reconnectAttempt = 0

    fun connect(serverIp: String, port: Int, token: String = "") {
        isUserDisconnected = false
        reconnectAttempt = 0
        lastServerIp = serverIp
        lastPort = port
        lastToken = token
        reconnectJob?.cancel()
        doConnect(serverIp, port)
    }

    private fun doConnect(serverIp: String, port: Int) {
        scope.launch {
            try {
                Log.d(TAG, "Attempting to connect to ws://$serverIp:$port")
                val request = Request.Builder()
                    .url("ws://$serverIp:$port")
                    .build()

                webSocket = client.newWebSocket(request, object : WebSocketListener() {
                    override fun onOpen(webSocket: WebSocket, response: Response) {
                        Log.d(TAG, "WebSocket opened")
                        reconnectAttempt = 0
                        if (lastToken.isNotEmpty()) {
                            val auth = JSONObject().apply {
                                put("type", "auth")
                                put("token", lastToken)
                            }
                            webSocket.send(auth.toString())
                        }
                        onConnected()
                    }

                    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                        Log.e(TAG, "WebSocket failure: ${t.message}", t)
                        onError(t.message ?: "Connection failed")
                        handleConnectionLost()
                    }

                    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                        Log.d(TAG, "WebSocket closed: code=$code, reason=$reason")
                        if (code == CLOSE_CODE_AUTH_FAILED) {
                            // Retrying with the same wrong token is pointless;
                            // stop and let the user fix it.
                            isUserDisconnected = true
                            onError("auth_failed")
                        }
                        handleConnectionLost()
                    }

                    override fun onMessage(webSocket: WebSocket, text: String) {
                        // Server only sends control messages (e.g. auth_ok)
                        Log.d(TAG, "Server message received")
                    }
                })
            } catch (e: Exception) {
                Log.e(TAG, "Connection error: ${e.message}", e)
                onError(e.message ?: "Connection error")
                handleConnectionLost()
            }
        }
    }

    private fun handleConnectionLost() {
        webSocket = null
        onDisconnected()
        if (!isUserDisconnected) {
            scheduleReconnect()
        }
    }

    private fun scheduleReconnect() {
        // Don't schedule if one is already pending
        if (reconnectJob?.isActive == true) return
        reconnectAttempt++
        // Exponential backoff: 3s, 6s, 12s, 24s, 48s, then capped at 60s
        val shift = (reconnectAttempt - 1).coerceAtMost(5)
        val delayMs = (RECONNECT_BASE_DELAY_MS shl shift).coerceAtMost(RECONNECT_MAX_DELAY_MS)
        Log.d(TAG, "Scheduling reconnect attempt $reconnectAttempt in ${delayMs}ms")
        onReconnecting(reconnectAttempt)
        reconnectJob = scope.launch {
            delay(delayMs)
            if (!isUserDisconnected) {
                doConnect(lastServerIp, lastPort)
            }
        }
    }

    fun disconnect() {
        Log.d(TAG, "Disconnecting")
        isUserDisconnected = true
        reconnectJob?.cancel()
        reconnectJob = null
        if (webSocket != null) {
            webSocket?.close(1000, "User disconnected")
            webSocket = null
        } else {
            // Already disconnected (e.g. mid-reconnect); notify UI directly
            onDisconnected()
        }
    }

    /**
     * Releases all resources. The client cannot be reused after this;
     * call from Activity.onDestroy().
     */
    fun close() {
        isUserDisconnected = true
        reconnectJob?.cancel()
        reconnectJob = null
        webSocket?.close(1000, "Client closed")
        webSocket = null
        scope.cancel()
        client.dispatcher.executorService.shutdown()
    }

    private fun sendMessage(json: JSONObject, description: String) {
        val ws = webSocket
        if (ws == null) {
            Log.w(TAG, "$description - not connected, dropping message")
            return
        }
        try {
            val sent = ws.send(json.toString())
            if (!sent) {
                Log.w(TAG, "$description - send failed, connection dead")
                handleConnectionLost()
            } else {
                Log.d(TAG, "$description - sent")
            }
        } catch (e: Exception) {
            Log.e(TAG, "$description - error: ${e.message}", e)
            handleConnectionLost()
        }
    }

    fun sendText(content: String) {
        val json = JSONObject().apply {
            put("type", "text")
            put("content", content)
        }
        // Log the length only - typed content must not end up in logcat
        sendMessage(json, "sendText (${content.length} chars)")
    }

    fun sendBackspace(count: Int) {
        val json = JSONObject().apply {
            put("type", "backspace")
            put("count", count)
        }
        sendMessage(json, "sendBackspace $count")
    }

    fun sendEnter() {
        val json = JSONObject().apply {
            put("type", "enter")
        }
        sendMessage(json, "sendEnter")
    }

    fun isConnected(): Boolean = webSocket != null
}
