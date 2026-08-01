curl --request POST \
  --url https://api.siliconflow.cn/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-cenbimztrqpkfijlcryqzerlnlswxmpvkfuihbjamkfeofwl" \
  -d '{
    "model": "deepseek-ai/DeepSeek-OCR",
    "messages": [
      {
        "role": "system",
        "content": "你是专业的OCR文字提取助手，请精准识别图片内所有文字，按原文顺序输出，不要添加多余解释、总结和翻译。"
      },
      {
        "role": "user",
        "content": [
          {
            "type": "image_url",
            "image_url": {
              "url": "https://www.w3.org/TR/clreq/images/en/romanization-basic.png",
              "detail": "high"
            }
          },
          {
            "type": "text",
            "text": "提取这张图片中的全部文字内容"
          }
        ]
      }
    ]
  }'