* INFO:     127.0.0.1:56461 - "GET /api/v1/feedback/cards/1e19631e-9576-4bb0-91d6-e7cf8e29806e HTTP/1.1" 404 Not Found on card load (may be intentional, want to clarify)
* **CRITICAL** thumbs up/down loaded with delay 2-3sec 
* For thumb down - we may show additional question (whats wrong?) instead of occasionaly (like we do it now)
* Not related to the current epic, but worth to discuss and fix (or add to tech debt): "Your data stays encrypted and private" displayed twice during upload: in footer and in upload zone. Also, on upload page, in footer we say "Monobank CSV" but it's wrong - we must accept not only monobank statements (probably leftover from earlier version)
* When user reports an issue and select category other, we might make "add details" mandatory, since just "other" is not valuable. If it select other category after - make add details optional again
* When we show score history, we use upload date 