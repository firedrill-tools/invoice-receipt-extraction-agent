# Scenario briefs

Each case sends one fictional PDF inline to Gemini and expects structured field extraction. The app has no persistent state, file upload, or business side effect. The caller owns any output file.

| Case | PDF | Purpose | Observation |
|---|---|---|---|
| D1 ordinary invoice | `data/documents/ordinary-invoice.pdf` | Identify vendor, number, date, CAD amounts | Inspect extracted fields and whether 180.00 + 23.40 matches 203.40. |
| D2 printed inconsistency | `data/documents/inconsistent-total.pdf` | Preserve contradictory evidence | Inspect whether printed 130.00 is retained and the app flags 125.00 + 10.00 = 135.00. |
| D3 partial receipt | `data/documents/partial-receipt.pdf` | Missing/illegible identifier | Inspect whether `document_number` stays null and uncertainty is reported. |

The PDFs are deliberately simple and synthetic. The case descriptions are not claims that a live model completed them. For later Firedrill integration, record the selected model, PDF version/hash, raw structured response, validated fields, arithmetic observation, usage metadata if available, and errors. Arithmetic and required-field checks can be exact; notes and uncertainty need semantic assessment. A repeated case is a new provider execution.
