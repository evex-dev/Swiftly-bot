from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

# 新しいモデルに変更
model_name = "alter-wang/bert-base-japanese-emotion-lily"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

# 感情ラベルのマッピングを追加
emotion_mapping = {
    0: 'amaze',
    1: 'anger',
    2: 'dislike',
    3: 'excite',
    4: 'fear',
    5: 'joy',
    6: 'like',
    7: 'relief',
    8: 'sad',
    9: 'shame'
}

def get_emotion_scores(text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        # このモデルはソフトマックス確率を使用する
        probabilities = F.softmax(logits, dim=1).squeeze().tolist()

    # 感情スコアを辞書形式で返す
    if isinstance(probabilities, list):
        # バッチサイズが1の場合
        scores = {emotion_mapping[i]: score for i, score in enumerate(probabilities)}
    else:
        # スカラー値の場合（確率が1つだけの場合）
        scores = {emotion_mapping[0]: probabilities}
        
    return scores