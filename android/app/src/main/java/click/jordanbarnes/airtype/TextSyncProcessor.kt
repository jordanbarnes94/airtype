package click.jordanbarnes.airtype

import java.text.BreakIterator

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

    private var pendingDeletedText: String? = null

    /**
     * Called before text changes. Mirrors TextWatcher.beforeTextChanged parameters.
     * Captures the substring about to be deleted so onTextChanged can count
     * grapheme clusters instead of raw UTF-16 code units.
     */
    fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {
        pendingDeletedText = if (s != null && count > 0) {
            s.substring(start, start + count)
        } else {
            null
        }
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
            val deletedText = pendingDeletedText
            val backspaceCount = if (deletedText != null) {
                countGraphemeClusters(deletedText)
            } else {
                before
            }
            messageSender.sendBackspace(backspaceCount)
            pendingDeletedText = null
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

    companion object {
        fun countGraphemeClusters(text: String): Int {
            val bi = BreakIterator.getCharacterInstance()
            bi.setText(text)
            var count = 0
            while (bi.next() != BreakIterator.DONE) count++
            return count
        }
    }
}
