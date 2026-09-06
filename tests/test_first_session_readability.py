from synapse.panel import message_formatter as mf


def test_headings_emphasis_and_ordered_steps_render():
    output = mf.format_response("## Lighting\n\n**Key light** and *fill*.\n\n1. Select the light\n2. Adjust intensity")
    assert "<h2" in output and "<strong>Key light</strong>" in output
    assert "<em>fill</em>" in output and "<ol" in output
    assert output.index("Lighting") < output.index("Key light") < output.index("Select the light")


def test_code_is_literal_and_does_not_become_nested_node_link():
    output = mf.format_response('```python\nnode = "/stage/light"\nvalue = "**literal** <tag>"\n```\n\nSelect /stage/light')
    assert output.count('href="node:/stage/light"') == 1
    assert "**literal** &lt;tag&gt;" in output
    assert '<a href="node:' not in output.split("<pre", 1)[1].split("</pre>", 1)[0]


def test_prose_html_escaped_links_safe_and_literal_code_escaped_once():
    output = mf.format_response('<img src="https://tracking.example/pixel"> [bad](javascript:alert) [Docs](https://example.com/docs) `a < b & c`')
    assert "<img" not in output
    assert "&lt;img" in output
    assert 'href="javascript:' not in output
    assert 'href="https://example.com/docs"' in output
    assert "a &lt; b &amp; c" in output


def test_tools_can_explicitly_supply_trusted_html():
    output = mf.format_response(mf.TrustedHtml('<table><tr><td>Tool receipt</td></tr></table>'))
    assert "<table><tr><td>Tool receipt" in output
