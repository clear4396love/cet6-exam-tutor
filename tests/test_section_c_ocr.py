import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "reading"))

from sectionC_load import careful_reading


def test_parse_passages_accepts_period_and_parenthesis_option_labels():
    chunk = """Questions 46 to 50 are based on the following passage.
Passage text.
46. Question one?
A. First option. B) Second option. C. Third option. D) Fourth option.
47. Question two?
A) First option. B. Second option. C) Third option. D. Fourth option."""

    result = careful_reading().parse_passage(chunk, {})

    assert result is not None
    assert result["questions"]["46"]["options"] == {
        "A": "First option.", "B": "Second option.",
        "C": "Third option.", "D": "Fourth option.",
    }
    assert result["questions"]["47"]["options"] == {
        "A": "First option.", "B": "Second option.",
        "C": "Third option.", "D": "Fourth option.",
    }


def test_parse_keys_reads_section_c_answers_without_losing_section_b_keys():
    pages = [SimpleNamespace(page_content="""KEYS
<table>
<tr><td>36</td><td>37</td><td>38</td><td>39</td><td>40</td><td>41</td><td>42</td><td>43</td><td>44</td><td>45</td></tr>
<tr><td>A</td><td>B</td><td>C</td><td>D</td><td>E</td><td>F</td><td>G</td><td>H</td><td>I</td><td>J</td></tr>
<tr><td>46</td><td>47</td><td>48</td><td>49</td><td>50</td><td>51</td><td>52</td><td>53</td><td>54</td><td>55</td></tr>
<tr><td>B</td><td>A</td><td>D</td><td>C</td><td>B</td><td>D</td><td>A</td><td>C</td><td>D</td><td>A</td></tr>
</table>""")]

    answers = careful_reading().parse_keys(pages)

    assert "".join(answers[n] for n in range(36, 46)) == "ABCDEFGHIJ"
    assert "".join(answers[n] for n in range(46, 56)) == "BADCBDACDA"


def test_save_refuses_to_wipe_cache_when_passages_incomplete():
    """切不出两篇 → 一个字都不许写。

    没有这条守卫时,save() 会把 {"passages": []} 写回去,把已有的好缓存清成空壳;
    扫描卷没有文字层时走的正是这条路(2020_7_1 重缓存时才补的)。
    """
    import json
    import tempfile

    import sectionC_load as sc

    tmp = tempfile.mkdtemp(prefix="sectionc_nosplit_")
    old_pdf, old_parsed = sc.PDF_DIR, sc.PARSED_DIR
    sc.PDF_DIR, sc.PARSED_DIR = tmp, tmp
    try:
        cache = Path(tmp) / "2020_7_1.json"
        good = {"year": 2020, "section_c": {"passages": [{"id": 1}, {"id": 2}]}}
        cache.write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
        before = cache.read_text(encoding="utf-8")

        # 假 PDF 在,但页里没有 "Section C" 分界 → 切不出两篇
        (Path(tmp) / "CET6_2020年7月_第1套_真题.pdf").write_bytes(b"x")
        parser = careful_reading()
        parser.pdf_load = lambda path: [SimpleNamespace(page_content="没有分界行的正文")]
        parser.save(2020, 7, 1)

        assert cache.read_text(encoding="utf-8") == before, "缓存被覆盖了"
    finally:
        sc.PDF_DIR, sc.PARSED_DIR = old_pdf, old_parsed
