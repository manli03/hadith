import requests
from google import genai
import json
import time
from typing import List, Dict, Optional, Any
import sys  # For writing loading animation to console
import threading
import os  # For creating directories
import subprocess
import signal
import concurrent.futures


def signal_handler(sig, frame):
    print("You pressed Ctrl+C!")
    # Save the error hadith numbers to a JSON file
    if error_hadith_numbers:
        with open("error_hadiths.json", "w", encoding="utf-8") as f:
            json.dump(error_hadith_numbers, f, indent=2, ensure_ascii=False)
        print(f"Error Hadith Numbers saved to: error_hadiths.json")  # Inform user
    else:
        print("No Error Hadiths found.")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def generate_content_with_timeout(client, model, contents, timeout=300):
    """
    Runs client.models.generate_content in a separate thread and enforces a timeout.
    :param client: The Gemini client instance.
    :param model: The model name.
    :param contents: The prompt or data to send.
    :param timeout: Timeout in seconds (default 300 seconds = 5 minutes).
    :return: The response from client.models.generate_content.
    :raises TimeoutError: If the call does not complete within the timeout.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.models.generate_content, model=model, contents=contents
        )
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError("Gemini API call timed out after 300 seconds")


def translate_hadith(
    hadith_data: Dict[str, Any],
    gemini_api_key: str,
    prompt: str,
    model_name: str = "gemini-1.5-flash-8b",
) -> Optional[Dict[str, Any]]:
    # """Translates a single Hadith data from English to Malay using Google Gemini."""

    client = genai.Client(api_key=gemini_api_key)
    combined_prompt = f"{prompt}\n\nData: {json.dumps(hadith_data, ensure_ascii=False)}"

    try:
        response = generate_content_with_timeout(
            client, model=model_name, contents=combined_prompt, timeout=300
        )

        # Added check to remove leading/trailing backticks and 'json' if present
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        try:
            translated_data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e}\nRaw Response: {response.text}")
            return None

        return translated_data

    except TimeoutError as e:
        print(f"TimeoutError: {e}")
        raise e
    except Exception as e:
        # Re-raise exception so process_hadiths can handle it.
        raise e


def fetch_book_data(book_name: str) -> Optional[Dict[str, Any]]:
    # """Fetches Hadith data from the specified API endpoint."""
    base_url = "https://github.com/AhmedBaset/hadith-json/raw/refs/heads/main/db/by_book/the_9_books/"
    api_url = base_url + f"{book_name}.json"

    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        return data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        raise e
    except (
        KeyError,
        json.JSONDecodeError,
    ) as e:  # Added more specific exception handling
        print(f"Error parsing API response: {e}")
        return None


def translate_chapter_name(
    chapter_name: str,
    gemini_api_key: str,
    prompt_chapter: str,
    model_index: int,
    models: List[str],
    resource_exhausted_count: int,
    attempts_limit: int = 20,
) -> tuple[Optional[str], int]:
    """Translates a single chapter name from English to Malay using Google Gemini."""

    attempts = 0
    translated_name: Optional[str] = None  # Initialize translated_name to None
    while attempts < attempts_limit:
        client = genai.Client(api_key=gemini_api_key)
        combined_prompt = f"{prompt_chapter}\n\nChapter Name: {chapter_name}"

        try:
            response = generate_content_with_timeout(
                client, model=models[model_index], contents=combined_prompt, timeout=300
            )
            translated_name = response.text.strip()  # Extract and strip whitespace
            return translated_name, model_index
        except TimeoutError as e:
            print(f"TimeoutError during chapter name translation: {e}")
            return (
                None,
                model_index,
            )  # Handle timeout specifically, return model_index
        except Exception as e:
            if "429 RESOURCE_EXHAUSTED" in str(e):
                resource_exhausted_count += 1
                print(f"    Resource exhausted. Count: {resource_exhausted_count}")
                if resource_exhausted_count >= 4:
                    model_index = (model_index + 1) % len(models)
                    print(f"    Switching to model: {models[model_index]}")
                    resource_exhausted_count = 0
                else:
                    print(
                        "    Waiting 10 seconds before retrying with the same model..."
                    )
                    time.sleep(10)
            else:
                print(f"Error translating chapter name: {e}")
                return (
                    None,
                    model_index,
                )  # return model_index and other values
            attempts += 1  # Increment attempt counter for retry
            time.sleep(2)  # Sleep a little before retrying
    print(
        f"Failed to translate chapter name '{chapter_name}' after {attempts_limit} attempts."
    )
    return (
        None,
        model_index,
    )  # return model_index and other values


def process_hadiths(
    book_name: str,
    chapter_id: int,
    gemini_api_key: str,
    prompt: str,
    error_hadith_numbers: list,
    model_index: int,
    models: List[str],
    resource_exhausted_count: int,
    all_hadiths_data: List[Dict[str, Any]],
) -> tuple[Optional[List[Dict[str, Any]]], int, int]:
    # """
    # Translates Hadith data, and returns a list of translated Hadiths.
    # """

    translated_hadiths = []
    hadiths_in_chapter = [h for h in all_hadiths_data if h["chapterId"] == chapter_id]
    total_hadiths = len(hadiths_in_chapter)
    successful_translations = 0

    print(f"  Translating {total_hadiths} Hadiths in Chapter {chapter_id}...")

    for i, hadith in enumerate(hadiths_in_chapter):
        hadith_id = hadith.get("id", "N/A")
        hadith_number = hadith.get("idInBook", "N/A")  # Use idInBook as Hadith number

        print(
            f"    Translating Hadith {i + 1}/{total_hadiths} (ID: {hadith_id}, Number: {hadith_number})...",
            end="",
        )

        loading_chars = ["\\", "|", "/", "-"]
        stop_loading = False
        loading_char_index = 0

        def animate_loading():
            nonlocal loading_char_index
            while not stop_loading:
                sys.stdout.write(
                    f"\r    Translating Hadith {i + 1}/{total_hadiths} (ID: {hadith_id}, Number: {hadith_number})... {loading_chars[loading_char_index % len(loading_chars)]}"
                )
                sys.stdout.flush()
                time.sleep(0.2)
                loading_char_index += 1

        loading_thread = threading.Thread(target=animate_loading)
        loading_thread.daemon = True
        loading_thread.start()

        # Prepare data for translation, only include what's necessary for the prompt
        translation_data = {
            "id": hadith.get("id", ""),
            "english_text": hadith.get("english", {}).get("text", ""),
            "arabic_text": hadith.get("arabic", ""),
            "narrator": hadith.get("english", {}).get("narrator", ""),
            "idInBook": hadith_number,  # added
        }

        translated_hadith = None
        attempts = 0
        while translated_hadith is None and attempts < 5:
            if attempts > 0:
                print(
                    f"    Retrying Hadith (Number: {hadith_number}) attempt [{attempts}/4] in 10 seconds..."
                )
                time.sleep(10)

            try:
                translated_hadith = translate_hadith(
                    translation_data,
                    gemini_api_key,
                    prompt,
                    model_name=models[model_index],
                )

            except TimeoutError as e:
                print(f"    TimeoutError during translation: {e}")
                continue  # Retry on timeout
            except Exception as e:
                if "429 RESOURCE_EXHAUSTED" in str(e):
                    resource_exhausted_count += 1
                    print(f"    Resource exhausted. Count: {resource_exhausted_count}")
                    if resource_exhausted_count >= 4:
                        model_index = (model_index + 1) % len(models)
                        print(f"    Switching to model: {models[model_index]}")
                        resource_exhausted_count = 0
                    else:
                        print(
                            "    Waiting 5 seconds before retrying with the same model..."
                        )
                        time.sleep(5)
                    continue
                else:
                    print(f"    Other Error during translation: {e}")
                    print(
                        "    Waiting 5 seconds before retrying with the same model..."
                    )
                    time.sleep(5)
                    continue
            attempts += 1

        stop_loading = True
        loading_thread.join()
        sys.stdout.write(
            f"\r    Translating Hadith {i + 1}/{total_hadiths} (ID: {hadith_id}, Number: {hadith_number})..."
        )
        sys.stdout.flush()

        if translated_hadith:
            # Include arabic_text in the translated output
            arabic_text = hadith.get("arabic", "")  # Get arabic_text if available
            translated_hadith["arabic_text"] = arabic_text

            translated_hadiths.append(translated_hadith)
            successful_translations += 1
            print(" Success!")
            resource_exhausted_count = 0  # Reset if success
        else:
            print(" Failed.")
            print(
                f"      Failed to translate hadith with id: {hadith.get('id', 'N/A')}"
            )
            error_hadith_numbers.append(
                hadith_number
            )  # Store the hadith number (idInBook)
            resource_exhausted_count = 0  # Reset if fail
        time.sleep(1)

    print(f"  Chapter {chapter_id} Translation complete.")
    print(
        f"    Successfully translated: {successful_translations}/{total_hadiths} Hadiths."
    )

    if successful_translations == 0:
        return (
            None,
            model_index,
            resource_exhausted_count,
        )  # Return None only if absolutely no translations succeeded.
    return translated_hadiths, model_index, resource_exhausted_count


def process_book(
    book_name: str,
    gemini_api_key: str,
    prompt: str,
    prompt_chapter: str,
    error_hadith_numbers: list,
):
    # """Processes all chapters of a book, fetches hadiths, translates them, and saves to JSON files."""
    book_data = fetch_book_data(book_name.lower())

    if book_data is None:
        print(f"Failed to fetch data for {book_name}.")
        return

    book_id = book_data["id"]
    book_title_en = book_data["metadata"]["english"]["title"]
    book_title_ar = book_data["metadata"]["arabic"]["title"]
    chapters = book_data["chapters"]
    all_hadiths_data = book_data["hadiths"]

    print(f"Processing Book: {book_title_en} (ID: {book_id})")

    # Initialize model-related variables *outside* the chapter loop
    model_index = 0
    models = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-exp",
        "gemini-2.0-flash-thinking-exp-01-21",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-flash-8b-exp-0924",
        "learnlm-1.5-pro-experimental",
    ]
    resource_exhausted_count = 0

    # Directory name for the book
    book_dir = f"hadiths/{book_name.replace(' ', '-').lower()}"

    # Load existing chapter names if the file exists
    chapter_filename = f"{book_dir}/chapter_names.json"
    translated_chapters: List[Dict[str, str]] = []
    if os.path.exists(chapter_filename):
        try:
            with open(chapter_filename, "r", encoding="utf-8") as f:
                book_data_from_file = json.load(f)  # Load entire structure
                translated_chapters = book_data_from_file.get(
                    "chapters", []
                )  # Access the 'chapters' list
            print(f"Loaded existing chapter names from {chapter_filename}")
        except json.JSONDecodeError:
            print(
                f"Warning: Could not decode JSON from {chapter_filename}. Starting with empty chapter list."
            )
            translated_chapters = []  # Initialize to an empty list

    # Create a set of already translated chapter IDs
    translated_chapter_ids = {chapter["id"] for chapter in translated_chapters}

    # First, translate and save chapter names
    for chapter in chapters:
        chapter_id = chapter["id"]
        chapter_title_en = (
            chapter["english"] if chapter["english"] else chapter["arabic"]
        )

        # Skip if already translated
        if chapter_id in translated_chapter_ids:
            print(
                f"Chapter {chapter_id}: {chapter_title_en} already translated. Skipping."
            )
            continue

        try:
            translated_title, model_index = translate_chapter_name(
                chapter_title_en,
                gemini_api_key,
                prompt_chapter,
                model_index,
                models,
                resource_exhausted_count,
            )
            if translated_title:
                translated_chapters.append(
                    {
                        "id": chapter_id,
                        "english": chapter_title_en,
                        "malay": translated_title,
                    }
                )  # Store the english title as well
                print(
                    f"Translated Chapter {chapter_id}: {chapter_title_en} -> {translated_title}"
                )
                time.sleep(1)  # Add a delay
            else:
                print(f"Failed to translate Chapter {chapter_id}: {chapter_title_en}")
        except Exception as e:
            print(f"Error processing chapter {chapter_id}: {e}")

    # Save translated chapter names to a JSON file
    # Prepare the data to be saved in the new structure
    data_to_save = {
        "id": book_data["id"],
        "metadata": book_data["metadata"],
        "chapters": translated_chapters,
    }

    # Save translated chapter names to a JSON file
    with open(chapter_filename, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, indent=2, ensure_ascii=False)
    print(f"Saved translated chapter names to {chapter_filename}")

    # Then, process and save hadiths for each chapter
    for chapter in chapters:
        chapter_id = chapter["id"]
        chapter_title_en = chapter["english"]
        print(f"Processing Chapter {chapter_id}: {chapter_title_en}")

        filename = f"{book_dir}/chapter_{chapter_id}.json"
        # Check if the JSON file already exists
        if os.path.exists(filename):
            print(
                f"JSON file already exists for {book_name} - Chapter {chapter_id}. Checking for missing hadiths..."
            )
            # Load existing hadiths
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    existing_hadiths = json.load(f)
            except json.JSONDecodeError:
                print(
                    f"Warning: Could not decode JSON from {filename}.  Starting with empty hadith list."
                )
                existing_hadiths = []

            # Extract translated hadiths to a set for easy checking
            existing_hadith_ids = {h["id"] for h in existing_hadiths}
            # Fetch hadiths for the current chapter
            chapter_hadiths = [
                h for h in all_hadiths_data if h["chapterId"] == chapter_id
            ]

            # Identify missing hadiths based on 'id'
            missing_hadiths = [
                h for h in chapter_hadiths if h["id"] not in existing_hadith_ids
            ]

            if missing_hadiths:
                print(f"Found {len(missing_hadiths)} missing hadiths.")

                # Translate only the missing hadiths
                (
                    translated_missing_hadiths,
                    model_index,
                    resource_exhausted_count,
                ) = process_hadiths(
                    book_name,
                    chapter_id,
                    gemini_api_key,
                    prompt,
                    error_hadith_numbers,
                    model_index,
                    models,
                    resource_exhausted_count,
                    missing_hadiths,
                )

                if translated_missing_hadiths:
                    print(
                        "Successfully translated missing hadiths. Appending to existing JSON."
                    )

                    # Append the translated missing hadiths to the existing data
                    existing_hadiths.extend(translated_missing_hadiths)

                    # Sort hadiths by ID
                    existing_hadiths.sort(key=lambda x: int(x["id"]))

                    # Save the updated JSON file
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(existing_hadiths, f, indent=2, ensure_ascii=False)
                    print(f"Appended translated hadiths to {filename}")
                else:
                    print(
                        "No missing hadiths were translated for {book_name} - Chapter {chapter_id}."
                    )
            else:
                print(
                    f"No missing hadiths found in {book_name} - Chapter {chapter_id}."
                )

            continue  # Skip to the next chapter after checking and appending.

        hadiths_in_chapter = [
            h for h in all_hadiths_data if h["chapterId"] == chapter_id
        ]
        (
            translated_hadiths,
            model_index,
            resource_exhausted_count,
        ) = process_hadiths(
            book_name,
            chapter_id,
            gemini_api_key,
            prompt,
            error_hadith_numbers,
            model_index,
            models,
            resource_exhausted_count,
            hadiths_in_chapter,
        )

        if translated_hadiths:
            # Save to a JSON file named after the chapter
            filename = f"{book_dir}/chapter_{chapter_id}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(translated_hadiths, f, indent=2, ensure_ascii=False)
            print(f"Saved translated hadiths to {filename}")
        else:
            print(f"No hadiths translated for {book_name} - Chapter {chapter_id}.")


# Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # Replace with your actual API key

TRANSLATION_PROMPT = """
You are a highly skilled translator specializing in Islamic texts. Your task is to translate Hadith data from English/Urdu to Malay (Malaysia), ensuring accuracy, cultural sensitivity, and preservation of the original message's religious and spiritual meaning.

**Instructions:**

1.  **Input:** You will receive Hadith data in JSON format, including fields such as `english_text`, `arabic_text`, `narrator`, and `idInBook`.

2.  **Translation:** Translate all relevant text fields into accurate and fluent Malay (Malaysia).
    *   Preserve the religious and spiritual meaning of the Hadith.
    *   Maintain consistency in terminology.
    *   Use standard Malay spelling and grammar.

3.  **Technical Terms:** Retain technical Islamic terms (e.g., *Sahih*, *Hadith*, names of prophets and companions) in their original form if a direct, equivalent Malay term does not exist or if using the original term is culturally preferred and understood by Malay speakers.

4.  **Title Generation:** Create a brief, meaningful title in Malay (Malaysia) that accurately summarizes the essence of the Hadith.  This should be stored in the `tajuk_hadith` field.

5.  **Field Completion:** Translate the following english field to malay and use this key instead "narrator" should be "perawi_melayu", and idInBook should be "hadith_number".

6.  **Output Format:** Return the translated data in JSON format, with the following structure(make sure to ensuring that the JSON is valid and parsable. Avoid unterminated strings, trailing commas, and invalid escape sequences that will cause a json decode error):

    {
        "id": ,
        "hadith_number": ,
        "tajuk_hadith": "",
        "perawi_melayu": "",
        "english_text": "",
        "arabic_text": "",
        "malay_translation": ""
    }

7.  **Handling Missing Data:** If data is missing for some section, create a suitable one for it in malay. and if the data is not available in the english_text field, please use the arabic_text field for translation. and put "" in the english_text field.

8.  **Contextual Understanding:**  Demonstrate a deep understanding of Islamic context when translating. Consider cultural nuances and avoid literal translations that may distort the intended meaning.

9.  Warning: Islamic Unicode characters may included in Hadith data field. Please ensure proper handling.Ensure that your JSON output uses UTF-8 encoding to preserve non-ASCII characters like Arabic.
"""

TRANSLATE_CHAPTER_PROMPT = """
You are a highly skilled translator specializing in Islamic texts. Your task is to translate chapter name from English to Malay (Malaysia), ensuring accuracy, cultural sensitivity, and preservation of the original message's religious and spiritual meaning.

**Instructions:**

1.  **Input:** You will receive chapter name in English.

2.  **Translation:** Translate the chapter name into accurate and fluent Malay (Malaysia).
    *   Preserve the religious and spiritual meaning of the chapter.
    *   Maintain consistency in terminology.
    *   Use standard Malay spelling and grammar.

3.  **Technical Terms:** Retain technical Islamic terms (e.g., *Sahih*, *Hadith*, names of prophets and companions) in their original form if a direct, equivalent Malay term does not exist or if using the original term is culturally preferred and understood by Malay speakers.

4. **Handling Missing Data:** If the data is not available in the english_text field, please use the arabic_text field for translation to both english and malay(malaysia).

5.  **Output:** Return only translated chapter name in malay.
"""

BOOKS = [
    "bukhari",
    "muslim",
    "abudawud",
    "tirmidhi",
    "nasai",
    "ibnmajah",
    "ahmed",
    "darimi",
    "malik",
]


# Main execution
try:
    if __name__ == "__main__":
        try:
            # Create a main directory to store all hadiths
            os.makedirs("hadiths", exist_ok=True)

            error_hadith_numbers = []  # Initialize list to store error hadith numbers

            for book_name in BOOKS:
                # Create book directory
                book_dir = f"hadiths/{book_name.replace(' ', '-').lower()}"
                os.makedirs(book_dir, exist_ok=True)

                process_book(
                    book_name,
                    GEMINI_API_KEY,
                    TRANSLATION_PROMPT,
                    TRANSLATE_CHAPTER_PROMPT,
                    error_hadith_numbers,
                )

            print("All books processed.")

            # Save the error hadith numbers to a JSON file
            if error_hadith_numbers:
                with open("error_hadiths.json", "w", encoding="utf-8") as f:
                    json.dump(error_hadith_numbers, f, indent=2, ensure_ascii=False)
                print(
                    f"Error Hadith Numbers saved to: error_hadiths.json"
                )  # Inform user
            else:
                print("No Error Hadiths found.")

        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print("Running check_link_status.py to check network connection...")
            subprocess.run(
                [
                    "python",
                    "check_link_status.py",
                ]
            )
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"A network error occurred: {e}")
            print("Running check_link_status.py to check network connection...")
            subprocess.run(
                [
                    "python",
                    "check_link_status.py",
                ]
            )
            sys.exit(1)

except KeyboardInterrupt:
    print("Script stopped by user!")
    # Save the error hadith numbers to a JSON file
    if error_hadith_numbers:
        with open("error_hadiths.json", "w", encoding="utf-8") as f:
            json.dump(error_hadith_numbers, f, indent=2, ensure_ascii=False)
        print(f"Error Hadith Numbers saved to: error_hadiths.json")  # Inform user
    else:
        print("No Error Hadiths found.")
    sys.exit(0)
