# Hadith Translations to Malay (Malaysia)

This repository contains translated Hadith texts in Malay, specifically tailored for the Malaysian audience. The source data is obtained from the excellent [AhmedBaset/hadith-json](https://github.com/AhmedBaset/hadith-json) repository. Translations are generated using the Gemini AI API (utilizing a free tier) using the `translate.py` Python script, focusing on accuracy, cultural sensitivity, and maintaining the spiritual meaning of the original texts.

**Goal:** To make authentic Islamic teachings more accessible to Malay-speaking Muslims in Malaysia.

**Key Features:**

*   **Automated Translation:**  The `translate.py` script automates the translation process using AI.
*   **High-Quality Translations:**  Leverages AI to provide accurate and fluent Malay translations.
*   **Cultural Adaptation:**  Ensures translations are culturally appropriate and relevant to the Malaysian context.
*   **Preservation of Meaning:** Strives to maintain the original spiritual and religious intent of the Hadith.
*   **Open Source:** This repository is open-source, allowing for community contributions and improvements.

## Hadith Collections Included:

The following Hadith collections are included in this repository:

1.  **Sahih al-Bukhari** (صحيح البخاري) - *The Most Authentic Source*
2.  **Sahih Muslim** (صحيح مسلم) - *Another Highly Regarded Collection*
3.  **Sunan Abi Dawud** (سنن أبي داود) - *A Collection Focusing on Legal Rulings*
4.  **Jami` at-Tirmidhi** (جامع الترمذي) - *Known for its Comprehensive Approach*
5.  **Sunan an-Nasa'i** (سنن النسائي) - *Emphasis on Authentic Chains of Narration*
6.  **Sunan Ibn Majah** (سنن ابن ماجه) - *A Valuable Addition to the Six Major Collections*
7.  **Muwatta Malik** (موطأ مالك) - *An Early Collection Emphasizing Practical Application*
8.  **Musnad Ahmad** (مسند أحمد) - *A Large Collection Organized by Narrator*
9.  **Sunan ad-Darimi** (سنن الدارمي) - *A Collection with a Unique Arrangement*

**Data Structure:**

Each Hadith collection is stored in its own directory within the `hadiths/` folder. Each directory contains:

*   **Chapter Files:** JSON files named `chapter_[chapter_id].json`, containing the translated Hadith for a specific chapter.
*   **Chapter Names File:** A JSON file named `chapter_names.json`, containing the metadata for the book (title, author, etc.) and a list of translated chapter names. This file has the following structure:

    ```json
    {
      "id": 1,
      "metadata": {
        "id": 1,
        "length": 7277,
        "arabic": {
          "title": "صحيح البخاري",
          "author": "الإمام محمد بن إسماعيل البخاري",
          "introduction": ""
        },
        "english": {
          "title": "Sahih al-Bukhari",
          "author": "Imam Muhammad ibn Ismail al-Bukhari",
          "introduction": ""
        }
      },
      "chapters": [
        {
          "id": 1,
          "english": "Revelation",
          "malay": "Wahyu"
        },
        {
          "id": 2,
          "english": "Belief",
          "malay": "Keimanan"
        }
      ]
    }
    ```

    *   `id`: The unique identifier for the book.
    *   `metadata`: Contains information about the book, including titles, authors, and introductions in Arabic, English, and Malay.
    *   `chapters`: An array of objects, where each object contains:
        *   `id`: The chapter ID.
        *   `english`: The chapter name in English.
        *   `malay`: The translated chapter name in Malay.

**Example Hadith Data (inside chapter JSON files):**

```json
[
    {
        "id": 123,
        "hadith_number": 45,
        "tajuk_hadith": "Keutamaan Bersedekah Secara Sembunyi",
        "perawi_melayu": "Diriwayatkan oleh Abu Hurairah RA",
        "english_text": "The Prophet (PBUH) said, 'The best charity is that which the right hand gives and the left hand does not know about.'",
        "arabic_text": "قال النبي صلى الله عليه وسلم: خير الصدقة ما كانت عن ظهر غنى، واليد العليا خير من اليد السفلى",
        "malay_translation": "Nabi SAW bersabda, 'Sebaik-baik sedekah adalah sedekah yang diberikan oleh tangan kanan dan tangan kiri tidak mengetahuinya.'"
    },
]
