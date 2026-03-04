package click.jordanbarnes.airtype

/**
 * Processes text changes and generates sync messages.
 * This is the core logic extracted from TextWatcher for testability.
 */
class TextSyncProcessor(private val messageSender: MessageSender) {

    interface MessageSender {
        fun sendText(content: String)
        fun sendBackspace(count: Int)
        fun sendEnter()
    }

    /**
     * Called when text changes. Mirrors TextWatcher.onTextChanged parameters.
     *
     * @param s The new text
     * @param start The start position of the change
     * @param before Number of characters that were replaced
     * @param count Number of new characters
     */
    fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
        if (s == null) return

        // Characters were deleted
        if (before > 0) {
            messageSender.sendBackspace(before)
        }

        // Characters were added
        if (count > 0) {
            val newText = s.substring(start, start + count)

            // Handle newlines (Enter key)
            if (newText.contains("\n")) {
                val parts = newText.split("\n")
                for (i in parts.indices) {
                    if (parts[i].isNotEmpty()) {
                        messageSender.sendText(parts[i])
                    }
                    if (i < parts.size - 1) {
                        messageSender.sendEnter()
                    }
                }
            } else {
                messageSender.sendText(newText)
            }
        }
    }
}
