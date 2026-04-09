try:
    print(expanded_query)
    expanded_query = "test"
except Exception as e:
    print(f"Error str: {str(e)}")
    print(f"Error repr: {repr(e)}")
