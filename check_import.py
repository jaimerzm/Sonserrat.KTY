try:
    import google.generativeai
    print("google.generativeai imported successfully")
except ModuleNotFoundError:
    print("Error: ModuleNotFoundError: No module named 'google.genai'")
except Exception as e:
    print(f"An unexpected error occurred: {e}")