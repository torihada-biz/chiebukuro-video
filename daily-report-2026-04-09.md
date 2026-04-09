# 日報 2026-04-09

## 実施タスク

### 1. Fish Audio TTS の日本語音質問題の調査・修正

フィードバック「TTSが聞き取れない」の根本原因を特定し修正した。

**根本原因（2件）:**

- **`clean-text`ライブラリの`clean()`関数** が内部で`unidecode`を呼び、日本語テキストを全てローマ字（ピンイン混じり）に変換していた
  - 例: `至急です` → `zhi ji desu`
- **絵文字除去の正規表現** `\U000024C2-\U0001F251` の範囲がCJK漢字・ひらがな・カタカナを包含しており、日本語文字を全削除していた

**修正内容:**
- `clean()`の使用を廃止し、Supplemental Planes (U+1F000以上) のみを対象とする正規表現に置き換え
- 記号除去ルールから`!`を除外（日本語の感嘆符を保持）

### 2. Fish Audio TTSの`language`パラメータ設定

- APIリクエストに`language: "ja"`を明示指定（自動推定に頼らない）
- `config.toml`から`fish_audio_language`を読み取る仕組みを追加
- デバッグログを追加し、TTSに渡されるテキストとパラメータを可視化

### 3. 動画の再生成・検証

修正後のパイプラインで3回動画を生成し、日本語TTSが正常に動作することを確認。

| 動画 | 質問 | 長さ |
|------|------|------|
| chiebukuro-fish-test.mp4 | 至急です、来年の3月までに50万貯める方法 | 26s |
| chiebukuro-ja-v2.mp4 | 至急です、来年の3月までに50万貯める方法 | 26s |
| chiebukuro-ja-v3.mp4 | 1番好きなハンバーガーは、どこの何のハンバーガーですか？ | 26s |

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `TTS/fish_audio.py` | `language`をconfig.tomlから読み取り、APIリクエストに反映。デバッグログ追加。mp3_bitrate 128→192 |
| `utils/voice.py` | `clean-text`の`clean()`廃止。絵文字除去を日本語安全な正規表現に置換。記号除去ルール修正 |
| `chiebukuro/scraper.py` | トップページURL修正、AnswerItem__Item__セレクタで回答抽出精度向上、面白さスコアリング追加 |
| `utils/.config.template.chiebukuro.toml` | `fish_audio_language`設定項目を追加 |
| `video_creation/final_video.py` | ffmpeg `drawtext`フィルタ依存を除去（fontconfig不要に） |
| `video_creation/voices.py` | `FishAudio`をTTSプロバイダに登録 |

### コミット履歴

```
5e74bd9 feat: Fish Audio TTSのlanguageをconfig.tomlから設定可能に
9c05364 fix: sanitize_textの日本語破壊バグを修正
bd0d82a fix: Fish Audio TTSにlanguage=ja明示指定を追加
bdcdfe4 feat: Fish Audio S2-Pro TTSエンジン追加
c3c88a2 fix: スクレイパーの回答抽出精度向上とdrawtext依存を除去
```

## 残タスク

- [ ] 動画の尺制御: 現在TTSの`max_length=60s`で打ち切りだが、ショート動画は60秒以内に収める明示的なガードが必要
- [ ] 複数回答の表示改善: 回答カード画像が長文の場合に文字切れする。テキスト量に応じたフォントサイズ自動調整
- [ ] 動画ファイルサイズの最適化: 現状47-85MB。H.264のCRF値調整やビットレート制御で10MB以下に圧縮
- [ ] 出力ファイル名の正規化: 日本語タイトルがそのままファイル名になり長すぎる場合がある
- [ ] GUI対応: `GUI.py`を知恵袋版に更新（現在はReddit版のまま）
- [ ] ボイスモデルの切り替え機能: 質問と回答で異なるボイスを使う（S2-Proのマルチスピーカー対応）
- [ ] CI/CDパイプライン: テスト自動化、定期的な動画生成ジョブ
