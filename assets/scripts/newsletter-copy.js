(function () {
    var btn = document.getElementById("newsletter-copy-btn");
    var status = document.getElementById("newsletter-copy-status");
    var body = document.getElementById("newsletter-body");
    if (!btn || !status || !body) return;

    function report(message) {
        status.textContent = message;
        status.hidden = false;
    }

    function selectBody() {
        // The next-best thing to an automatic copy: the text is already selected, so a manual
        // copy is just Ctrl/Cmd+C, not a click-and-drag across the whole newsletter.
        try {
            var selection = window.getSelection();
            var range = document.createRange();
            range.selectNodeContents(body);
            selection.removeAllRanges();
            selection.addRange(range);
            return true;
        } catch (e) {
            return false;
        }
    }

    function fallbackToPlainText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(
                function () {
                    report("Copied as plain text — paste into Buttondown.");
                },
                function () {
                    var selected = selectBody();
                    report(selected
                        ? "Couldn't copy automatically — the text below is selected, press Ctrl/Cmd+C to copy it."
                        : "Couldn't copy automatically — select the text below and copy it yourself.");
                }
            );
        } else {
            var selected = selectBody();
            report(selected
                ? "Couldn't copy automatically — the text below is selected, press Ctrl/Cmd+C to copy it."
                : "Couldn't copy automatically — select the text below and copy it yourself.");
        }
    }

    btn.addEventListener("click", function () {
        var html = body.innerHTML;
        var text = body.innerText;

        // Buttondown's compose box is a rich editor, so a copy carrying real HTML (headings,
        // bold, links) pastes in already formatted, the same way pasting from a Google Doc
        // would. Every modern browser also lets us hand over a plain-text fallback in the same
        // clipboard write, for whatever the paste target prefers or if it strips HTML.
        if (window.ClipboardItem && navigator.clipboard && navigator.clipboard.write) {
            var item = new ClipboardItem({
                "text/html": new Blob([html], { type: "text/html" }),
                "text/plain": new Blob([text], { type: "text/plain" }),
            });
            navigator.clipboard.write([item]).then(
                function () {
                    report("Copied — paste into Buttondown.");
                },
                function () {
                    fallbackToPlainText(text);
                }
            );
        } else {
            fallbackToPlainText(text);
        }
    });
})();
