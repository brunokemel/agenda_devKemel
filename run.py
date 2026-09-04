import os

if __name__ == "__main__":
    os.environ.setdefault("PORT", "5055")
    from app import main

    main()
