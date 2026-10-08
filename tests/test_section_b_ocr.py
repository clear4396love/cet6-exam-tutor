from types import SimpleNamespace

from reading.sectionB_load import paragraph_matching


def _page(text: str) -> SimpleNamespace:
    return SimpleNamespace(page_content=text)


def test_extract_reading_accepts_bracketed_paragraph_labels():
    pages = [
        _page(
            """Part III Reading Comprehension
Section B
[A] First paragraph.
Continuation of A.
[B] Second paragraph.
36. A matching statement.
Section C
Translation
"""
        )
    ]

    paragraphs, questions = paragraph_matching().extract_reading(pages)

    assert paragraphs == {
        "A": "First paragraph. Continuation of A.",
        "B": "Second paragraph.",
    }
    assert questions == {36: "A matching statement."}


def test_parse_keys_accepts_bracketed_answer_ranges():
    pages = [
        _page(
            """【参考答案】
【36-40】CJBAK 【41-45】EMHDL
"""
        )
    ]

    assert paragraph_matching().parse_keys(pages) == {
        36: "C",
        37: "J",
        38: "B",
        39: "A",
        40: "K",
        41: "E",
        42: "M",
        43: "H",
        44: "D",
        45: "L",
    }


def test_parse_keys_rejects_incomplete_answer_range():
    pages = [_page("【36-40】CJBA")]

    assert paragraph_matching().parse_keys(pages) == {}


def test_parse_keys_accepts_html_answer_table():
    pages = [
        _page(
            """## KEYS
<table><tr><td>36</td><td>37</td><td>38</td><td>39</td><td>40</td><td>41</td><td>42</td><td>43</td><td>44</td><td>45</td></tr>
<tr><td>G</td><td>D</td><td>J</td><td>H</td><td>B</td><td>I</td><td>C</td><td>L</td><td>E</td><td>N</td></tr></table>
"""
        )
    ]

    assert paragraph_matching().parse_keys(pages) == {
        36: "G",
        37: "D",
        38: "J",
        39: "H",
        40: "B",
        41: "I",
        42: "C",
        43: "L",
        44: "E",
        45: "N",
    }
