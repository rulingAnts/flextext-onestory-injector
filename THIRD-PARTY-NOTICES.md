# Third-party notices

## OneStory Editor

`src/injector/ose_serializer.py` adapts the element and attribute inventory, the
emission order, and the conditional-attribute rules from the `GetXml` serialization
in OneStory Editor:

- `StoryEditor/VerseData.cs` — `VerseData.GetXml`, `LineData.AddXml`, `AddXmlField`
- `StoryEditor/StoryData.cs` — the `<story>` element, `RemoveCarriageReturns`

Source: <https://github.com/bobeaton/OneStoryEditor>

MIT permits this adaptation. Its sole condition is that the copyright notice and the
permission notice below travel with the derived work, which is the purpose of this
file. MIT is compatible with the AGPL, so the combined work is distributed under
AGPL-3.0-or-later while SIL's original remains MIT for everyone else.

> The MIT License (MIT)
>
> Copyright 2021 SIL International
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of
> this software and associated documentation files (the "Software"), to deal in the
> Software without restriction, including without limitation the rights to use,
> copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
> Software, and to permit persons to whom the Software is furnished to do so,
> subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
> FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
> COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
> AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
> WITH THE SOFTWARE OR OTHER DEALINGS IN THE SOFTWARE.

### What is *not* adapted

The byte formatting — UTF-8 with no BOM, CRLF between elements, two-space indent,
`<x />` with a leading space, and no XML prologue — is **not** taken from OneStory
Editor. It reproduces the defaults of .NET's `XmlTextWriter`, which is what
`OseXmlSerializer` ends up using, and was established by measuring real project
files. No SIL code was consulted for it.

## Alignment rules

The vernacular/gloss alignment rules (paired `[B&B …]` removal, `***` as an explicit
hole, orphan folding) are ported from `docs/js/interlinear-align.js` in
`ose-interlinear-viewer`, which is AGPL-3.0-or-later and has the same copyright
holder as this project. No third-party rights are involved.
