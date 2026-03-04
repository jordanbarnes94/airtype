package click.jordanbarnes.airtype

import android.content.Context
import android.util.AttributeSet
import android.view.ActionMode
import android.view.Menu
import android.view.MenuItem
import android.view.MotionEvent
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputConnection
import android.view.inputmethod.InputConnectionWrapper
import androidx.appcompat.widget.AppCompatEditText

/**
 * A custom EditText that enforces append-only semantics: the cursor is always
 * kept at the end of the text, and all new input is appended there.
 *
 * WHY THIS EXISTS
 * ===============
 * AirType's TextWatcher diff algorithm (TextSyncProcessor) relies on text
 * changes happening at the end. If the cursor can be positioned mid-text, a
 * keystroke inserts at the wrong place and the diff produces garbled output
 * (e.g. spurious backspaces + wrong text sent to the PC). This class ensures
 * the invariant: cursor == end of text, always.
 *
 * THE ANDROID IME PROTOCOL
 * ========================
 * On Android, the soft keyboard (IME) communicates with the focused view through
 * the InputConnection interface. The view creates an InputConnection in
 * onCreateInputConnection(); the IME holds a reference to it and calls methods
 * on it to commit text, delete characters, move the cursor, etc.
 * Ref: https://developer.android.com/reference/android/view/inputmethod/InputConnection
 *
 * The key methods the IME uses:
 *   commitText(text, newCursorPos)  — insert/replace text at current cursor
 *   deleteSurroundingText(n, m)     — delete n chars before / m chars after cursor
 *   setSelection(start, end)        — move cursor / set selection without changing text
 *
 * The view's side of the protocol:
 *   onSelectionChanged(selStart, selEnd)  — called by the framework whenever the
 *                                           cursor position or selection changes
 *
 * WHAT WE INTERCEPT AND WHY
 * =========================
 * We wrap the InputConnection (via InputConnectionWrapper) to observe and
 * react to deleteSurroundingText and commitText calls. We also override
 * onSelectionChanged to detect keyboard-driven cursor movements (swipe
 * gestures) and decide when to snap the cursor back to end.
 *
 * GBOARD SWIPE GESTURES — THE CRITICAL DISTINCTION
 * =================================================
 * Gboard has two swipe gestures that move the cursor:
 *
 *   1. SPACEBAR SWIPE (cursor repositioning)
 *      Slide a finger along the spacebar to move the cursor left/right.
 *      Gboard calls setSelection(newPos, newPos) — selStart == selEnd,
 *      meaning the cursor moves but no text is selected. No deletion follows.
 *      We want to snap back to end immediately so subsequent typing and
 *      backspaces still go to the right place.
 *
 *   2. BACKSPACE SWIPE (swipe-delete)
 *      Press and hold the backspace key, then slide left to sweep over
 *      characters/words you want to delete. Release to confirm the deletion.
 *      Gboard calls setSelection(selStart, selEnd) with selStart != selEnd —
 *      text gets highlighted/selected as you swipe. When you release,
 *      deleteSurroundingText(n, 0) fires (or commitText("", 1) as an
 *      alternative depending on the Gboard version).
 *      We must NOT snap the cursor back while the user is still holding/
 *      swiping, because the snap would move the selection anchor to end and
 *      the subsequent deleteSurroundingText would delete from the wrong place.
 *      Instead, we wait for the deletion call and snap after it completes.
 *
 * So: selStart != selEnd  →  swipe-delete gesture in progress  →  wait
 *     selStart == selEnd, cursor != end  →  spacebar/cursor swipe  →  snap now
 *
 * PREVIOUS APPROACH (WHY IT WAS WRONG)
 * =====================================
 * The previous implementation used a 150 ms timer: onSelectionChanged would
 * schedule a snap, and deleteSurroundingText would cancel it if it arrived
 * within the window. This failed for long swipe-hold-delete gestures: if the
 * user held the swipe position still for >150 ms (very common when scanning
 * for the right deletion point), no new onSelectionChanged events fired, the
 * timer expired, the cursor snapped to end, and the subsequent
 * deleteSurroundingText deleted from the wrong position.
 *
 * The current approach is event-driven with no timer: it keys off the
 * selStart != selEnd signal to know a swipe-delete is in progress, and only
 * snaps once the deletion (or next text insertion) actually fires.
 */
class AppendOnlyEditText @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = android.R.attr.editTextStyle
) : AppCompatEditText(context, attrs, defStyleAttr) {

    /**
     * Called when the keyboard sends a delete event but the EditText is already
     * empty. AirType uses this to forward a backspace keystroke to the PC even
     * when there is nothing left to delete locally.
     *
     * This fires from our InputConnection override of deleteSurroundingText.
     * It does NOT fire from the key-event path (KEYCODE_DEL via setOnKeyListener
     * in MainActivity) — that path has its own empty-text check.
     */
    var onBackspaceWhenEmpty: (() -> Unit)? = null

    init {
        // setTextIsSelectable(false) suppresses the long-press text-selection
        // handles and the "Select all / Cut / Copy / Paste" floating toolbar that
        // Android shows when the user long-presses on text. Without this, a long
        // press would create a selection range, breaking our cursor-at-end invariant.
        // Ref: https://developer.android.com/reference/android/widget/TextView#setTextIsSelectable(boolean)
        setTextIsSelectable(false)

        // isLongClickable = false prevents the view from responding to long-press
        // gestures at all. This is a belt-and-suspenders measure alongside
        // setTextIsSelectable(false): even if the selectable flag is ignored by some
        // OS version, a non-long-clickable view won't start selection mode.
        isLongClickable = false

        // customSelectionActionModeCallback intercepts the floating "action mode"
        // toolbar that appears when text is selected (Cut / Copy / Paste / Select all).
        // Returning false from onCreateActionMode tells the system not to show the
        // toolbar at all. Without this, a user could select text via accessibility
        // services or hardware keyboard shortcuts (Shift+arrow) and trigger Cut/Copy,
        // which doesn't hurt anything but looks confusing.
        // Ref: https://developer.android.com/reference/android/view/ActionMode.Callback
        customSelectionActionModeCallback = object : ActionMode.Callback {
            override fun onCreateActionMode(mode: ActionMode?, menu: Menu?) = false
            override fun onPrepareActionMode(mode: ActionMode?, menu: Menu?) = false
            override fun onActionItemClicked(mode: ActionMode?, item: MenuItem?) = false
            override fun onDestroyActionMode(mode: ActionMode?) {}
        }

        // customInsertionActionModeCallback does the same for the "insertion point"
        // toolbar — the one with "Paste" that appears when the user taps the cursor
        // handle on an empty selection. Blocking it keeps the UI clean.
        customInsertionActionModeCallback = object : ActionMode.Callback {
            override fun onCreateActionMode(mode: ActionMode?, menu: Menu?) = false
            override fun onPrepareActionMode(mode: ActionMode?, menu: Menu?) = false
            override fun onActionItemClicked(mode: ActionMode?, item: MenuItem?) = false
            override fun onDestroyActionMode(mode: ActionMode?) {}
        }
    }

    /**
     * Intercepts touch events to prevent the user from repositioning the cursor
     * by tapping mid-text.
     *
     * When a finger touches an EditText, Android calls super.onTouchEvent() which
     * computes the character position under the finger and calls setSelection() to
     * move the cursor there. We can't suppress that computation (it's deep inside
     * the layout code), but we can immediately move the cursor back.
     *
     * We use post {} (schedule on the next UI-thread message loop iteration) rather
     * than calling moveCursorToEnd() synchronously inside onTouchEvent, because the
     * framework may set the selection *after* onTouchEvent returns (e.g. in response
     * to the ACTION_UP event in the focus / click pipeline). Deferring one frame
     * ensures our setSelection(end) is the last one applied.
     *
     * We snap on both ACTION_DOWN and ACTION_UP to cover:
     *   ACTION_DOWN — first contact; prevents any visible cursor jump.
     *   ACTION_UP   — end of tap; covers cases where framework defers setSelection.
     *
     * We deliberately do NOT intercept ACTION_MOVE here. Touch-drag events during
     * a swipe-delete or swipe gesture originate from the keyboard's touch surface,
     * not from touches on the EditText itself, so ACTION_MOVE on the EditText only
     * happens during a genuine finger drag on the text view (which we don't want to
     * support anyway).
     */
    override fun onTouchEvent(event: MotionEvent): Boolean {
        val result = super.onTouchEvent(event)

        if (event.action == MotionEvent.ACTION_UP || event.action == MotionEvent.ACTION_DOWN) {
            post { moveCursorToEnd() }
        }

        return result
    }

    /**
     * Called by the framework whenever the cursor position or selection range
     * changes, regardless of whether the change came from the user touching the
     * view, the IME calling setSelection(), or our own setSelection() call.
     * Ref: https://developer.android.com/reference/android/widget/TextView#onSelectionChanged(int,%20int)
     *
     * We use this to distinguish two keyboard swipe gestures and react
     * appropriately (see class-level doc for the full explanation):
     *
     *   selStart != selEnd  →  A text selection exists. This is the signature of
     *                          Gboard's swipe-delete gesture: as the user slides
     *                          their finger left over the backspace key, Gboard
     *                          progressively selects (highlights) the characters
     *                          to be deleted. We do nothing here and wait for the
     *                          deletion to arrive via deleteSurroundingText or
     *                          commitText("", 1).
     *
     *   selStart == selEnd,    Cursor moved but no selection — this is Gboard's
     *   cursor != end      →   spacebar swipe (slide finger on space bar to move
     *                          cursor). No deletion will follow. We snap back to
     *                          end immediately (via post{}) so that the next
     *                          keystroke or backspace operates at the correct
     *                          position.
     *
     * Why post{} and not a direct setSelection() call here?
     * The framework can fire onSelectionChanged re-entrantly from within other
     * selection-setting operations (e.g. commitText triggers it). Calling
     * setSelection() directly inside onSelectionChanged risks infinite loops or
     * corrupting ongoing IME state. Posting defers our setSelection() to the next
     * message loop iteration, safely after the current framework call completes.
     *
     * The third case (selStart == selEnd == len, i.e. cursor already at end) is
     * the normal state after typing or after one of our own moveCursorToEnd()
     * calls. We do nothing.
     */
    override fun onSelectionChanged(selStart: Int, selEnd: Int) {
        super.onSelectionChanged(selStart, selEnd)
        val len = text?.length ?: 0
        when {
            // Swipe-delete gesture in progress: text is selected.
            // Wait for deleteSurroundingText / commitText("", 1) to confirm deletion.
            selStart != selEnd -> { /* do nothing */ }

            // Spacebar-swipe cursor reposition: cursor moved but no selection.
            // Snap back to end so the next input goes to the right place.
            selStart != len -> post { moveCursorToEnd() }

            // selStart == selEnd == len: cursor is already at end. Nothing to do.
        }
    }

    /**
     * Wraps the base InputConnection to intercept delete and commit operations.
     *
     * InputConnectionWrapper is a decorator pattern: it proxies all calls to the
     * real InputConnection (returned by super.onCreateInputConnection) while
     * letting us override specific methods. We pass `true` as the `mutable`
     * argument so the wrapper re-delegates to the updated base IC if the IME
     * refreshes it (important for some keyboards that recreate the IC mid-session).
     * Ref: https://developer.android.com/reference/android/view/inputmethod/InputConnectionWrapper
     */
    override fun onCreateInputConnection(outAttrs: EditorInfo): InputConnection? {
        val baseConnection = super.onCreateInputConnection(outAttrs) ?: return null
        return object : InputConnectionWrapper(baseConnection, true) {

            /**
             * Called by the IME to delete characters around the cursor.
             * `beforeLength` = chars to delete before cursor (to the left).
             * `afterLength`  = chars to delete after cursor (to the right).
             * Ref: https://developer.android.com/reference/android/view/inputmethod/InputConnection#deleteSurroundingText(int,%20int)
             *
             * This fires in two scenarios:
             *
             *   REGULAR BACKSPACE
             *   The user taps the backspace key normally. Gboard calls
             *   deleteSurroundingText(1, 0) to remove one character before the
             *   cursor. No cursor movement precedes this call.
             *
             *   SWIPE-DELETE (end of gesture)
             *   The user lifted their finger after a swipe-delete gesture.
             *   Throughout the swipe, Gboard was building a selection
             *   (onSelectionChanged with selStart != selEnd). Now it calls
             *   deleteSurroundingText(n, 0) where n is the number of
             *   selected characters, deleting them all at once.
             *
             * Empty-text check:
             *   If the EditText is already empty and the IME sends a delete, there
             *   is nothing to delete locally. We invoke onBackspaceWhenEmpty so
             *   MainActivity can forward a backspace keystroke to the Windows PC.
             *   We return true (consumed) without calling super to avoid a no-op
             *   delete that could confuse the IME's internal state tracking.
             *
             * Snap after deletion:
             *   After super.deleteSurroundingText() the text is shorter and the
             *   cursor is at the position where deletion ended — which is generally
             *   not the new end of text (e.g. if the user deleted words from the
             *   middle of the text via swipe). We post a moveCursorToEnd() to snap
             *   back to end on the next frame, after the framework has finished
             *   updating the text/selection state.
             */
            override fun deleteSurroundingText(beforeLength: Int, afterLength: Int): Boolean {
                if (text?.isEmpty() == true && beforeLength > 0) {
                    onBackspaceWhenEmpty?.invoke()
                    return true
                }
                val result = super.deleteSurroundingText(beforeLength, afterLength)
                post { moveCursorToEnd() }
                return result
            }

            /**
             * Identical in purpose to deleteSurroundingText, but counts in Unicode
             * code points rather than UTF-16 chars. Required for emoji and other
             * supplementary-plane characters that are represented as surrogate pairs
             * in Java/Kotlin's Char (UTF-16).
             *
             * Most keyboards call deleteSurroundingText for ASCII/Latin text and
             * deleteSurroundingTextInCodePoints for emoji. We mirror the same logic
             * in both to be safe.
             * Ref: https://developer.android.com/reference/android/view/inputmethod/InputConnection#deleteSurroundingTextInCodePoints(int,%20int)
             */
            override fun deleteSurroundingTextInCodePoints(beforeLength: Int, afterLength: Int): Boolean {
                if (text?.isEmpty() == true && beforeLength > 0) {
                    onBackspaceWhenEmpty?.invoke()
                    return true
                }
                val result = super.deleteSurroundingTextInCodePoints(beforeLength, afterLength)
                post { moveCursorToEnd() }
                return result
            }

            /**
             * Called by the IME to insert text at the current cursor position,
             * or to delete a selection by inserting an empty string.
             * Ref: https://developer.android.com/reference/android/view/inputmethod/InputConnection#commitText(java.lang.CharSequence,%20int)
             *
             * This fires in three scenarios:
             *
             *   NORMAL TYPING
             *   The user taps a key. Gboard calls commitText("a", 1) to insert the
             *   character. `newCursorPosition = 1` means "place cursor 1 position
             *   after the end of the inserted text" (i.e. at the new end).
             *   Before calling super, we synchronously snap the cursor to end. This
             *   is the safety net for the spacebar-swipe case: if a spacebar swipe
             *   left the cursor off-end and the user immediately types a character,
             *   our onSelectionChanged post{} snap may not have executed yet (it's
             *   deferred one frame). By snapping synchronously here, we guarantee
             *   the character is always appended at the end, not mid-text.
             *
             *   WORD SUGGESTION / GLIDE-TYPING RESULT
             *   Gboard commits an entire word via commitText("hello ", 1). Same
             *   handling as normal typing — snap first, then insert.
             *
             *   SELECTION DELETION VIA commitText("", 1)
             *   Some Gboard versions (and some Android releases) use
             *   commitText("", 1) instead of deleteSurroundingText to remove a
             *   selected region. An empty string replaces the selection, effectively
             *   deleting the selected text. After this, the cursor is at selStart
             *   (not at end). We post a moveCursorToEnd() snap after the deletion.
             *   We do NOT snap synchronously here (unlike the non-empty case) because
             *   the text change hasn't been fully committed to the Spannable yet
             *   at the point of our return; posting defers until the next frame when
             *   it is safe to call setSelection().
             */
            override fun commitText(text: CharSequence?, newCursorPosition: Int): Boolean {
                if (!text.isNullOrEmpty()) {
                    // Synchronously snap before inserting. This guarantees text
                    // always lands at end even if a prior post{} snap hasn't fired yet.
                    moveCursorToEnd()
                }
                val result = super.commitText(text, newCursorPosition)
                if (text.isNullOrEmpty()) {
                    // Deletion via commitText("", 1). Snap to end after the deletion.
                    post { moveCursorToEnd() }
                }
                return result
            }
        }
    }

    /**
     * Moves the cursor to the end of the current text.
     *
     * setSelection(start, end) sets both the cursor position and the selection
     * range. Passing the same value for start and end collapses the selection
     * to a cursor (no text highlighted).
     * Ref: https://developer.android.com/reference/android/widget/TextView#setSelection(int)
     *
     * The guard (checking selectionStart/selectionEnd first) prevents a no-op
     * setSelection() call when the cursor is already at end. This matters because
     * setSelection() triggers onSelectionChanged, which would post another
     * moveCursorToEnd(), creating an infinite loop. The guard breaks the cycle.
     */
    private fun moveCursorToEnd() {
        text?.let {
            if (selectionStart != it.length || selectionEnd != it.length) {
                setSelection(it.length)
            }
        }
    }

    /**
     * Returning true here hides the cursor-drag handle (the teardrop handle that
     * appears below the cursor and lets the user drag the cursor to a new position).
     * If we returned false the handle would be hidden, but we keep the visual
     * cursor (blinking bar) visible so the user can see where they are typing.
     *
     * Note: despite the method name, returning true means the cursor IS visible.
     * The name is confusing; think of it as "isCursorShown". The drag handle
     * suppression is a side effect of keeping the cursor visible while having
     * setTextIsSelectable(false) set.
     */
    override fun isCursorVisible(): Boolean = true

    /**
     * Intercepts context menu actions triggered by hardware keyboard shortcuts
     * (e.g. Ctrl+A for Select All, Ctrl+C for Copy, Ctrl+X for Cut).
     *
     * The customSelectionActionModeCallback in init{} blocks the *floating toolbar*
     * for mouse/touch selection, but keyboard shortcuts bypass that path and call
     * onTextContextMenuItem directly. We handle them here:
     *
     *   Cut / Copy   — consume (return true = handled) without doing anything.
     *                  The user can't usefully cut/copy from this append-only box.
     *   Select All   — would normally select all text; instead we move cursor to
     *                  end and claim we handled it, preventing the selection.
     *   Paste / etc. — fall through to super; paste is harmless (it appends text
     *                  which the TextWatcher will diff and sync normally).
     */
    override fun onTextContextMenuItem(id: Int): Boolean {
        return when (id) {
            android.R.id.cut -> true
            android.R.id.copy -> true
            android.R.id.selectAll -> {
                moveCursorToEnd()
                true
            }
            else -> super.onTextContextMenuItem(id)
        }
    }
}
