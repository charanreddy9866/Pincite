from app.chronology import extract_dates_offline
from app.ingest import chunk_text
from app.redact import redact
from app.verify import quote_in_text


class TestRedaction:
    def test_redacts_identifiers(self):
        text, counts = redact(
            "SSN 123-45-6789, card 4111 1111 1111 1111, Account No. 004417889213, "
            "call (305) 555-0142 or write maria@example.com"
        )
        for secret in ["123-45-6789", "4111 1111 1111 1111", "004417889213", "555-0142", "maria@example.com"]:
            assert secret not in text
        assert counts == {"SSN": 1, "CARD": 1, "ACCOUNT": 1, "PHONE": 1, "EMAIL": 1}

    def test_leaves_legal_identifiers_alone(self):
        text = "Case No. 1:25-cv-04417, serial NW5-22-118734, filed 03/03/2025, Bates NORTHWIND-0004417, $849.00"
        assert redact(text) == (text, {})

    def test_card_needs_valid_checksum(self):
        _, counts = redact("order 4111 1111 1111 1112")
        assert "CARD" not in counts


class TestQuoteVerification:
    PAGE = "Our thermal test report came back on August 2, 2021.\nIt showed the door-latch harness running more than\n30 percent above the design temperature."

    def test_exact_and_reflowed_quotes_pass(self):
        assert quote_in_text("thermal test report came back on August 2, 2021", self.PAGE)
        assert quote_in_text("harness running more than 30 percent above", self.PAGE)

    def test_smart_quotes_and_ellipsis(self):
        page = "Linda said \"keep shipping\" and we'll revisit the redesign in January."
        assert quote_in_text("Linda said “keep shipping” and we’ll revisit", page)
        assert quote_in_text("Linda said ... revisit the redesign in January", page)

    def test_fabricated_or_reordered_quotes_fail(self):
        assert not quote_in_text("the harness was within the design specification", self.PAGE)
        assert not quote_in_text("30 percent above ... thermal test report came back", self.PAGE)

    def test_quote_across_transcript_line_numbers(self):
        page = "11 A. Our thermal test report came back on August 2, 2021.\n12    It showed the door-latch harness running"
        assert quote_in_text("came back on August 2, 2021. It showed the door-latch harness", page)
        assert quote_in_text("came back on August 2, 2021. 12 It showed the door-latch harness", page)
        # numbers inside a sentence are still required to match
        assert not quote_in_text("running 12 percent above", "the harness running 30 percent above spec")

    def test_too_short_to_count(self):
        assert not quote_in_text("August", self.PAGE)


def test_chunks_overlap_and_keep_words_whole():
    text = " ".join(f"word{i}" for i in range(400))
    chunks = chunk_text(text, size=200, overlap=40)
    assert len(chunks) > 5
    assert all(len(c) <= 200 for c in chunks)
    assert chunks[0].split()[-1] in chunks[1].split()  # overlap carried forward
    assert " ".join(chunks).split()[0] == "word0"


def test_offline_date_extraction():
    events = extract_dates_offline(
        "Our report came back on August 2, 2021. Rev. C went into production in April 2023. "
        "The claim was filed 01/12/2024."
    )
    got = {(e["date"], e["precision"]) for e in events}
    assert got == {("2021-08-02", "day"), ("2023-04-01", "month"), ("2024-01-12", "day")}
    assert all(quote_in_text(e["quote"], "Our report came back on August 2, 2021. Rev. C went into production "
                                          "in April 2023. The claim was filed 01/12/2024.") for e in events)
