<a name="readme-top"></a>

<div align="center">

# MindsHub

**वह एकीकृत वर्कस्पेस जहाँ ओपन-सोर्स मॉडल आपके लिए काम पूरा करते हैं।**

_AI से असली काम करवाएँ। कभी भी मॉडल बदलें — जो कुछ आपने बनाया है, वह सब बना रहता है।_

[![Release](https://img.shields.io/github/v/release/mindsdb/minds?logo=github&label=release)](https://github.com/mindsdb/minds/releases)
[![Stars](https://img.shields.io/github/stars/mindsdb/minds?logo=github)](https://github.com/mindsdb/minds/stargazers)
[![License: MIT](https://img.shields.io/github/license/mindsdb/minds)](#-लाइसेंस)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%20–%203.13-brightgreen.svg)](https://www.python.org/downloads/)

[वेबसाइट](https://mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[दस्तावेज़](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[वेब ऐप](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[मूल्य निर्धारण](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) ·
[Discord](https://mindshub.ai/discord)

<p align="center">
  <sub>अन्य भाषाएँ: <a href="README.md">English</a> · <a href="README.zh.md">中文</a> · <a href="README.es.md">Español</a> · <a href="README.pt.md">Português</a></sub>
</p>

</div>

<p align="center">
  <img width="640" height="480" alt="cowork" src="https://github.com/user-attachments/assets/048761b8-aa77-4506-9c4d-32e2fdecbb60" />
</p>

**MindsHub Cowork** वह एकीकृत वर्कस्पेस है जहाँ आप पूरे प्रोजेक्ट्स सौंप सकते हैं — ऐप्स, वेबसाइट्स, रिसर्च, विश्लेषण, रिपोर्टिंग, शेड्यूल्ड ऑपरेशंस — और तैयार, शेयर करने-लायक नतीजे पाते हैं। अपना डेटा कनेक्ट करें, काम को किसी भी मॉडल (ओपन या प्रोप्राइटरी) पर रूट करें, ओपन-सोर्स एजेंट चलाएँ, और उनके आउटपुट को प्रकाशित करने-योग्य वेब ऐप्लिकेशंस में बदलें। यह ओपन सोर्स है और कहीं भी चलता है — आपकी मशीन पर, आपके VPC में, या होस्टेड ऐप में।

यह रिपॉज़िटरी **प्लेटफ़ॉर्म सुपरप्रोजेक्ट** है: यह डेस्कटॉप/वेब ऐप, एजेंट बैकएंड, और डेटा इंजन को एक साथ जोड़ता है, ताकि आप पूरा स्टैक सोर्स से बना और चला सकें।

## शुरुआत करें

जो आपके लिए सही हो, चुनें:

- **वेब — कुछ भी इंस्टॉल करने की ज़रूरत नहीं।** **[console.mindshub.ai](https://console.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)** खोलें और साइन इन करें।
- **macOS.** [डेस्कटॉप ऐप डाउनलोड करें](https://downloads.mindsdb.com/mindshub-cowork/mac/mindshub-cowork-latest.pkg) (`.pkg`)।
- **Windows.** [डेस्कटॉप ऐप डाउनलोड करें](https://downloads.mindsdb.com/mindshub-cowork/windows/mindshub-cowork-latest.exe) (`.exe`)।
- **Linux.** [सोर्स से बिल्ड करें](#सोर्स-से-बिल्ड-करें)।

शुरू करना फ्री है। Pro में सभी फ्रंटियर मॉडल्स और प्राइवेट आर्टिफैक्ट्स जुड़ते हैं — [मूल्य निर्धारण](https://mindshub.ai/pricing?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) देखें।

## आप क्या कर सकते हैं

हर नॉलेज वर्कर के लिए — क्रिएटर्स, स्ट्रैटेजिस्ट्स, और ऑपरेटर्स:

- **ऑटोमेट करें** पढ़ने-लिखने से जुड़े दोहराव वाले, मल्टी-स्टेप काम: रिपोर्ट्स, मॉनिटरिंग, बार-बार होने वाले वर्कफ़्लो, और शेड्यूल्ड ऑपरेशंस।
- **बनाएँ** इंटरनल AI टूल्स और आर्टिफैक्ट्स — ऐप्स, डैशबोर्ड्स, डेक्स, डॉक्युमेंट्स, एनालिसिस — इंजीनियरिंग के बिना, और अपनी टीम के साथ शेयर करने के लिए एक लाइव URL पर पब्लिश करें।

## इसमें क्या शामिल है

- **कनेक्टेड डेटा।** एक सुरक्षित वॉल्ट BigQuery, Postgres, Gmail, Drive, HubSpot, Notion, और Linear जैसे सिस्टम्स को जोड़ता है। क्रेडेंशियल्स हर कनेक्शन के हिसाब से सीमित रहते हैं — एजेंट्स कभी भी असली की (raw key) नहीं देखते।
- **मॉडल राउटर (Model Router)।** फ्रंटियर मॉडल्स (Claude, GPT, Gemini) और ओपन मॉडल्स (DeepSeek, Qwen, Kimi) के बीच बिना हर प्रोवाइडर के लिए अलग की सेट किए स्विच करें।
- **ओपन एजेंट्स।** इंटरचेंजेबल ओपन-सोर्स हार्नेस चलाएँ — Anton (डिफ़ॉल्ट) और Hermes — जिन्हें ड्रॉपडाउन से बदला जा सकता है।
- **आर्टिफैक्ट्स।** एजेंट के आउटपुट को डॉक्युमेंट्स, डैशबोर्ड्स, ऐप्स और कोड में बदलें, और लाइव URL पर पब्लिश करें।
- **मेमोरी, स्किल्स और शेड्यूलिंग।** सेशन्स के बीच याद रखने वाली मेमोरी, दोबारा इस्तेमाल होने वाली स्किल लाइब्रेरी, और शेड्यूल पर चलने वाले टास्क।

## सोर्स से बिल्ड करें

**1. रिपॉज़िटरी क्लोन करें**

```bash
git clone --recurse-submodules https://github.com/mindsdb/minds.git
cd minds
```

**2. डिपेंडेंसीज़ इंस्टॉल करें**

```bash
make setup
```

**3. चलाएँ**

| मोड | कमांड |
|---|---|
| हॉट रीलोड के साथ डेस्कटॉप ऐप (Electron) | `make dev` या `make watch` |
| हॉट रीलोड के साथ ब्राउज़र में वेब ऐप | `make dev-web` |
| प्रोडक्शन बिल्ड | `make build` |
| macOS के लिए पैकेज करें | `make dist-mac` |
| Windows के लिए पैकेज करें | `make dist-win` |
| लोकल अनकमिटेड सोर्स से macOS `.app` बनाएँ | `make pack-local` |
| सभी लोकल इंस्टॉल्स + डेटा मिटाएँ (शुरुआत से) | `make flush` |

> **शुरुआत से:** `make flush` लोकल रनटाइम (`cowork-server` uv टूल और `backend/*/.venv`) हटा देता है और `~/.anton` (प्रोवाइडर कीज़) व `~/.cowork` (डेटाबेस, hermes, प्रोजेक्ट्स) में ऐप स्टेट डिलीट कर देता है। इसका उपयोग शुरुआत से इंस्टॉल फ़्लो टेस्ट करने या टूटे हुए इंस्टॉल से रिकवर करने के लिए करें। यह पुष्टि माँगता है — पुष्टि स्किप करने के लिए `FORCE=1` पास करें। अगला `make setup` या ऐप लॉन्च सब कुछ फिर से इंस्टॉल कर देता है। ⚠️ इससे आपकी बातचीत (conversations) और सेव्ड कीज़ डिलीट हो जाती हैं।

### फ़ीचर ब्रांच पर काम करना (सबमॉड्यूल्स)

यह रिपॉज़िटरी एक सुपरप्रोजेक्ट है जो हर मॉड्यूल (`frontend`, `backend/core_api`, `backend/core_agent`, `backend/data-vault`) को एक कमिट पर पिन करता है। `git status` को गंदा किए बिना या पिन्स को लेकर उलझे बिना मॉड्यूल ब्रांच पर काम करने के लिए:

**1. अपनी ब्रांच चुनें** एक (gitignored) `dev.env` में (टेम्प्लेट से कॉपी करें):

```bash
cp dev.env.example dev.env      # फिर सेट करें REF=feat/my-thing (या हर मॉड्यूल के लिए API_REF=…)
```

**2. `make` इसे फ़ॉलो करता है** — एक ही सेटिंग, दोनों रन-पाथ के लिए:

| कमांड | यह क्या करता है |
|---|---|
| `make use` | सभी सबमॉड्यूल्स में `dev.env` की ब्रांच चेकआउट करता है |
| `make dev` / `make watch` | लोकल सोर्स के खिलाफ़ हॉट रीलोड के साथ Electron ऐप चलाता है |
| `make dev-web` | लोकल सोर्स के खिलाफ़ हॉट रीलोड के साथ वेब SPA चलाता है |
| `make server` + `make app` | कॉन्फ़िगर की गई ब्रांच से डेस्कटॉप सर्वर (फिर से) इंस्टॉल करता है, फिर लॉन्च करता है |
| `make server-local` + `make app-local` | **लोकल अनकमिटेड सोर्स** से डेस्कटॉप सर्वर इंस्टॉल करता है, फिर लॉन्च करता है |
| `make pack-local` | लोकल अनकमिटेड सोर्स से macOS `.app` बनाता है (push की ज़रूरत नहीं) |
| `make refs` | दिखाता है कि अगला रन किन रेफ़्स का उपयोग करेगा |
| `make baseline` | सबमॉड्यूल्स को पिन किए गए कमिट्स पर रीसेट करता है |
| `make pin` | मौजूदा सबमॉड्यूल कमिट्स को सुपरप्रोजेक्ट के पिन्स के रूप में रिकॉर्ड करता है (एक जानबूझकर किया गया कमिट) |

सबमॉड्यूल्स `ignore = all` के साथ कॉन्फ़िगर किए गए हैं, इसलिए आपका ब्रांच वाला काम कभी भी सुपरप्रोजेक्ट में बदलाव के रूप में नहीं दिखता — पेरेंट रिपॉज़िटरी का `git status` हमेशा साफ़ रहता है। पिन्स **केवल** `make pin` से बदलते हैं। पूरा वर्कफ़्लो [`CLAUDE.md`](CLAUDE.md) में देखें।

## कहीं भी डिप्लॉय करें

Cowork फ्लेक्सिबल डिप्लॉयमेंट के लिए बनाया गया है — **क्लाउड, VPC, ऑन-प्रेम, एयर-गैप्ड, और हाइब्रिड** इंफ़्रास्ट्रक्चर — ताकि आपका अपने इंफ़्रास्ट्रक्चर, मॉडल्स, परमिशन्स, और डेटा पर पूरा नियंत्रण बना रहे।

## मदद और सहायता

- **सवाल पूछें** — [Discord कम्युनिटी](https://mindshub.ai/discord) से जुड़ें।
- **बग रिपोर्ट करें** — रीप्रोडक्शन स्टेप्स के साथ एक [GitHub issue](https://github.com/mindsdb/minds/issues) खोलें।
- **दस्तावेज़ पढ़ें** — गाइड्स, सेटअप, और API [docs.mindshub.ai](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) पर।
- **एंटरप्राइज़ SLA या कस्टम डिप्लॉयमेंट** — [टीम से संपर्क करें](https://mindshub.ai/contact?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)।

## 🤝 योगदान करें

Cowork ओपन सोर्स है और योगदान का स्वागत है — कोड, इंटीग्रेशन्स, दस्तावेज़, बग रिपोर्ट्स, और फ़ीचर आइडियाज़। सेटअप के लिए [दस्तावेज़](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme) पढ़ें, [ओपन इश्यूज़](https://github.com/mindsdb/minds/issues) ब्राउज़ करें, और [Discord](https://mindshub.ai/discord) पर हाय कहें।

## 🔒 सुरक्षा

कोई सुरक्षा खामी (vulnerability) मिली? कृपया कोई पब्लिक issue **न** खोलें। हमारी [सुरक्षा नीति](https://github.com/mindsdb/minds/security) के ज़रिए इसे प्राइवेट तौर पर रिपोर्ट करें।

## 📚 संसाधन

- [दस्तावेज़](https://docs.mindshub.ai/?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [ब्लॉग](https://mindshub.ai/blog?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [ब्रांड गाइडलाइंस और प्रेस किट](https://mindshub.ai/press-kit?utm_source=github&utm_medium=repo-readme&utm_campaign=minds-readme)
- [Discord कम्युनिटी](https://mindshub.ai/discord)

## 📄 लाइसेंस

यह रिपॉज़िटरी [MIT लाइसेंस](LICENSE) के तहत जारी की गई है। बंडल किए गए कॉम्पोनेंट्स अपने-अपने लाइसेंस से गवर्न होते हैं — विवरण के लिए हर सबमॉड्यूल की रिपॉज़िटरी देखें।

<p align="right">(<a href="#readme-top">ऊपर वापस जाएँ</a>)</p>
