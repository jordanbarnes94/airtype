package click.jordanbarnes.airtype

import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class TextSyncProcessorTest {

    private lateinit var processor: TextSyncProcessor
    private val messages = mutableListOf<String>()

    private val mockSender = object : TextSyncProcessor.MessageSender {
        override fun sendText(content: String) {
            messages.add("TEXT:$content")
        }

        override fun sendBackspace(count: Int) {
            messages.add("BACKSPACE:$count")
        }

        override fun sendEnter() {
            messages.add("ENTER")
        }
    }

    @Before
    fun setup() {
        messages.clear()
        processor = TextSyncProcessor(mockSender)
    }

    @Test
    fun `normal typing sends text`() {
        // User types "a"
        processor.onTextChanged("a", 0, 0, 1)
        assertEquals(listOf("TEXT:a"), messages)
    }

    @Test
    fun `typing multiple characters sends text`() {
        // User types "hello" (e.g., paste or glide)
        processor.onTextChanged("hello", 0, 0, 5)
        assertEquals(listOf("TEXT:hello"), messages)
    }

    @Test
    fun `backspace sends backspace`() {
        // User deletes 1 character from "hello"
        processor.beforeTextChanged("hello", 4, 1, 0)
        processor.onTextChanged("hell", 4, 1, 0)
        assertEquals(listOf("BACKSPACE:1"), messages)
    }

    @Test
    fun `backspace emoji sends single backspace`() {
        // User deletes 😀 (2 UTF-16 code units, 1 grapheme cluster)
        val textBefore = "hello😀"
        processor.beforeTextChanged(textBefore, 5, 2, 0)
        processor.onTextChanged("hello", 5, 2, 0)
        assertEquals(listOf("BACKSPACE:1"), messages)
    }

    @Test
    fun `backspace flag emoji sends single backspace`() {
        // User deletes 🇦🇺 (4 UTF-16 code units, 1 grapheme cluster)
        val flag = "\uD83C\uDDE6\uD83C\uDDFA" // 🇦🇺
        val textBefore = "hi$flag"
        processor.beforeTextChanged(textBefore, 2, 4, 0)
        processor.onTextChanged("hi", 2, 4, 0)
        assertEquals(listOf("BACKSPACE:1"), messages)
    }

    @Test
    fun `backspace without beforeTextChanged falls back to raw count`() {
        // If beforeTextChanged wasn't called, fall back to before count
        processor.onTextChanged("hell", 4, 1, 0)
        assertEquals(listOf("BACKSPACE:1"), messages)
    }

    @Test
    fun `autocorrect sends backspaces then text`() {
        // "teh" autocorrects to "the" - 3 chars replaced with 3 chars
        processor.beforeTextChanged("teh", 0, 3, 3)
        processor.onTextChanged("the", 0, 3, 3)
        assertEquals(listOf("BACKSPACE:3", "TEXT:the"), messages)
    }

    @Test
    fun `glide typing word sends text`() {
        // Glide type "hello" after "hi " - adds 5 chars
        processor.onTextChanged("hi hello", 3, 0, 5)
        assertEquals(listOf("TEXT:hello"), messages)
    }

    @Test
    fun `enter key sends enter`() {
        // User presses enter
        processor.onTextChanged("hello\n", 5, 0, 1)
        assertEquals(listOf("ENTER"), messages)
    }

    @Test
    fun `text with newline sends text then enter`() {
        // Paste "hello\nworld"
        processor.onTextChanged("hello\nworld", 0, 0, 11)
        assertEquals(listOf("TEXT:hello", "ENTER", "TEXT:world"), messages)
    }

    @Test
    fun `multiple newlines handled correctly`() {
        processor.onTextChanged("a\n\nb", 0, 0, 4)
        assertEquals(listOf("TEXT:a", "ENTER", "ENTER", "TEXT:b"), messages)
    }

    @Test
    fun `null text does nothing`() {
        processor.onTextChanged(null, 0, 0, 0)
        assertTrue(messages.isEmpty())
    }

    @Test
    fun `no change does nothing`() {
        processor.onTextChanged("hello", 0, 0, 0)
        assertTrue(messages.isEmpty())
    }
}
