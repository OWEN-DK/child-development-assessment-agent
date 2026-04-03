def test():
    try:
        print(expanded_query)
    except Exception as e:
        print(f"Error str: {str(e)}")
        print(f"Error repr: {repr(e)}")
    expanded_query = "test"
test()
