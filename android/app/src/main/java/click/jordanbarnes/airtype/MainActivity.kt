package click.jordanbarnes.airtype

import android.content.Context
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.util.Log
import android.view.KeyEvent
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding

class MainActivity : AppCompatActivity() {
    companion object {
        private const val TAG = "AirType"
        private const val PREFS_NAME = "AirTypePrefs"
        private const val KEY_LAST_IP = "last_ip"
        private const val KEY_LAST_PORT = "last_port"
        private const val DEFAULT_IP = "192.168.1.100"
        private const val DEFAULT_PORT = "8765"
    }

    private lateinit var ipInput: EditText
    private lateinit var portInput: EditText
    private lateinit var connectButton: Button
    private lateinit var statusText: TextView
    private lateinit var statusDot: View
    private lateinit var textInput: AppendOnlyEditText
    private lateinit var clearButton: ImageButton
    private lateinit var connectionCard: LinearLayout

    private var webSocketClient: WebSocketClient? = null
    private var isConnected = false
    private var isReconnecting = false
    private var ignoreTextChanges = false
    private var suppressKeyBackspace = false

    private val textSyncProcessor = TextSyncProcessor(object : TextSyncProcessor.MessageSender {
        override fun sendText(content: String) {
            webSocketClient?.sendText(content)
        }
        override fun sendBackspace(count: Int) {
            webSocketClient?.sendBackspace(count)
        }
        override fun sendEnter() {
            webSocketClient?.sendEnter()
        }
    })

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)

        // Apply system bar and keyboard insets as padding
        val rootView = findViewById<LinearLayout>(R.id.rootLayout)
        ViewCompat.setOnApplyWindowInsetsListener(rootView) { view, windowInsets ->
            val insets = windowInsets.getInsets(
                WindowInsetsCompat.Type.systemBars() or
                WindowInsetsCompat.Type.displayCutout() or
                WindowInsetsCompat.Type.ime()
            )
            view.updatePadding(
                left = insets.left,
                top = insets.top,
                right = insets.right,
                bottom = insets.bottom
            )
            val imeVisible = windowInsets.isVisible(WindowInsetsCompat.Type.ime())
            val hideForTyping = imeVisible && textInput.hasFocus()
            connectionCard.visibility = if (hideForTyping) View.GONE else View.VISIBLE
            WindowInsetsCompat.CONSUMED
        }

        // Find views
        ipInput = findViewById(R.id.ipInput)
        portInput = findViewById(R.id.portInput)
        connectButton = findViewById(R.id.connectButton)
        statusText = findViewById(R.id.statusText)
        statusDot = findViewById(R.id.statusDot)
        textInput = findViewById(R.id.textInput)
        clearButton = findViewById(R.id.clearButton)
        connectionCard = findViewById(R.id.connectionCard)

        // Load saved values
        ipInput.setText(loadPref(KEY_LAST_IP, DEFAULT_IP))
        portInput.setText(loadPref(KEY_LAST_PORT, DEFAULT_PORT))

        // Re-evaluate connection card visibility when focus moves between inputs
        val focusListener = View.OnFocusChangeListener { _, _ ->
            val imeVisible = ViewCompat.getRootWindowInsets(rootView)
                ?.isVisible(WindowInsetsCompat.Type.ime()) == true
            connectionCard.visibility =
                if (imeVisible && textInput.hasFocus()) View.GONE else View.VISIBLE
        }
        textInput.onFocusChangeListener = focusListener
        ipInput.onFocusChangeListener = focusListener
        portInput.onFocusChangeListener = focusListener

        // Set up click listeners
        connectButton.setOnClickListener { toggleConnection() }
        clearButton.setOnClickListener {
            ignoreTextChanges = true
            textInput.setText("")
            ignoreTextChanges = false
        }

        setupWebSocketClient()
        setupTextWatcher()
        setupBackspaceHandler()

        // Handle soft keyboard backspace on empty text via InputConnection
        textInput.onBackspaceWhenEmpty = {
            if (isConnected) {
                webSocketClient?.sendBackspace(1)
                suppressKeyBackspace = true
                textInput.post { suppressKeyBackspace = false }
                Log.d(TAG, "Backspace on empty (InputConnection) - sent to Windows")
            }
        }
    }

    private fun toggleConnection() {
        if (isConnected || isReconnecting) {
            webSocketClient?.disconnect()
        } else {
            val ip = ipInput.text.toString().trim()
            val portStr = portInput.text.toString().trim()
            val port = portStr.toIntOrNull() ?: 8765

            if (ip.isEmpty()) {
                Toast.makeText(this, "Enter server IP", Toast.LENGTH_SHORT).show()
                return
            }

            Log.d(TAG, "Connecting to $ip:$port")
            updateStatus(null) // Connecting state
            savePref(KEY_LAST_IP, ip)
            savePref(KEY_LAST_PORT, portStr)
            webSocketClient?.connect(ip, port)
        }
    }

    private fun updateStatus(connected: Boolean?) {
        when (connected) {
            true -> {
                isConnected = true
                isReconnecting = false
                statusText.text = getString(R.string.connected)
                statusText.setTextColor(getColor(R.color.connected))
                statusDot.setBackgroundResource(R.drawable.status_dot_connected)
                connectButton.text = getString(R.string.disconnect)
                textInput.hint = getString(R.string.text_input_hint)
                textInput.isFocusable = true
                textInput.isFocusableInTouchMode = true
                textInput.isEnabled = true
                textInput.requestFocus()
            }
            false -> {
                isConnected = false
                isReconnecting = false
                statusText.text = getString(R.string.disconnected)
                statusText.setTextColor(getColor(R.color.text_secondary))
                statusDot.setBackgroundResource(R.drawable.status_dot_disconnected)
                connectButton.text = getString(R.string.connect)
                textInput.hint = getString(R.string.text_input_hint_disconnected)
                textInput.isEnabled = false
                textInput.isFocusable = false
                textInput.isFocusableInTouchMode = false
                textInput.clearFocus()
            }
            null -> {
                // Connecting state
                statusText.text = getString(R.string.connecting)
                statusText.setTextColor(getColor(R.color.primary))
            }
        }
    }

    private fun setupWebSocketClient() {
        webSocketClient = WebSocketClient(
            onConnected = {
                runOnUiThread { updateStatus(true) }
            },
            onDisconnected = {
                runOnUiThread { updateStatus(false) }
            },
            onReconnecting = { attempt ->
                runOnUiThread { updateStatusReconnecting(attempt) }
            },
            onError = { error ->
                Log.e(TAG, "WebSocket error: $error")
                runOnUiThread {
                    val isDisconnectError = error.contains("Broken pipe", ignoreCase = true) ||
                            error.contains("connection abort", ignoreCase = true) ||
                            error.contains("Connection reset", ignoreCase = true)
                    if (!isDisconnectError) {
                        Toast.makeText(this, "Error: $error", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        )
    }

    private fun updateStatusReconnecting(attempt: Int) {
        isConnected = false
        isReconnecting = true
        statusText.text = getString(R.string.reconnecting, attempt)
        statusText.setTextColor(getColor(R.color.primary))
        statusDot.setBackgroundResource(R.drawable.status_dot_disconnected)
        connectButton.text = getString(R.string.disconnect)
    }

    private fun setupTextWatcher() {
        textInput.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {
                if (ignoreTextChanges || !isConnected) return
                textSyncProcessor.beforeTextChanged(s, start, count, after)
            }

            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                if (ignoreTextChanges || !isConnected) return
                textSyncProcessor.onTextChanged(s, start, before, count)
                if (before > 0 && s?.isEmpty() == true) {
                    suppressKeyBackspace = true
                    textInput.post { suppressKeyBackspace = false }
                }
            }

            override fun afterTextChanged(s: Editable?) {}
        })
    }

    private fun setupBackspaceHandler() {
        // Handle backspace when text is empty (needed for hardware/Bluetooth keyboards)
        textInput.setOnKeyListener { _, keyCode, event ->
            if (keyCode == KeyEvent.KEYCODE_DEL && event.action == KeyEvent.ACTION_DOWN) {
                if (suppressKeyBackspace) {
                    Log.d(TAG, "Backspace (key event) suppressed - already handled")
                    return@setOnKeyListener true
                }
                if (textInput.text?.isEmpty() == true && isConnected) {
                    webSocketClient?.sendBackspace(1)
                    Log.d(TAG, "Backspace on empty - sent to Windows")
                    return@setOnKeyListener true
                }
            }
            false
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocketClient?.disconnect()
    }

    private fun loadPref(key: String, default: String): String {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(key, default) ?: default
    }

    private fun savePref(key: String, value: String) {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(key, value).apply()
    }
}
