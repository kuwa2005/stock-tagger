# サードパーティライセンス

本プロジェクトは以下のオープンソースコンポーネントを使用しています。
各コンポーネントのライセンス条項に従って利用しています。

---

## 1. Florence-2

- **用途**: 画像キャプション・タグ生成
- **モデル**: florence-community/Florence-2-base-ft（Microsoft Florence-2 ベース）
- **ライセンス**: MIT License
- **著作権**: Copyright (c) Microsoft Corporation
- **参照**: https://huggingface.co/florence-community/Florence-2-base-ft

```
MIT License

Copyright (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE
```

---

## 2. RAM++ (Recognize Anything Model++)

- **用途**: 画像タグ生成（`ram/` ディレクトリに組み込み）
- **プロジェクト**: https://github.com/xinyu1205/recognize-anything
- **モデル**: xinyu1205/recognize-anything-plus-model
- **ライセンス**: Apache License 2.0
- **著作権**: Copyright (c) 2022 OPPO
- **変更**: 本プロジェクトで統合・利用のため一部修正を加えています。

```
Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

Copyright (c) 2022 OPPO

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## 3. BERT (ram/models/bert.py)

- **用途**: RAM++ のテキストエンコーダ
- **元コード**: https://github.com/huggingface/transformers
- **ライセンス**: BSD-3-Clause
- **著作権**: Copyright (c) 2022, salesforce.com, inc.

```
BSD 3-Clause License

Copyright (c) 2022, salesforce.com, inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

## 4. ViT (ram/models/vit.py)

- **用途**: RAM++ の画像エンコーダ
- **ライセンス**: BSD-3-Clause
- **著作権**: Copyright (c) 2022, salesforce.com, inc.

上記 BERT と同様の BSD-3-Clause が適用されます。

---

## 5. Swin Transformer (ram/models/swin_transformer.py)

- **用途**: RAM++ の画像エンコーダ
- **ライセンス**: MIT License
- **著作権**: Copyright (c) 2021 Microsoft

```
MIT License

Copyright (c) 2021 Microsoft

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE
```

---

## 参照リンク

| コンポーネント | リンク |
|----------------|--------|
| Florence-2 | https://huggingface.co/florence-community/Florence-2-base-ft |
| RAM++ | https://github.com/xinyu1205/recognize-anything |
| RAM++ モデル | https://huggingface.co/xinyu1205/recognize-anything-plus-model |
