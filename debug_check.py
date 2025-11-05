with open('src/import_cars/scrapers/mobile_de.py', 'rb') as f:
    lines = f.readlines()
    for i in range(245, 250):
        if i < len(lines):
            line = lines[i]
            print(f'Line {i+1}: {line}')
