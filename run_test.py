import time
from urllib.parse import unquote
from Scraping import get_wikipedia_links, filter_links_by_person

if __name__ == '__main__':
    url = "https://fr.wikipedia.org/wiki/Emmanuel_Macron"
    print("Collecting links...")
    links = get_wikipedia_links(url)
    print(f"Total links collected: {len(links)}")

    max_workers = 20
    print(f"Filtering links with {max_workers} workers...")
    t0 = time.time()
    people = filter_links_by_person(links, max_workers=max_workers)
    dt = time.time() - t0
    print(f"Found {len(people)} person links in {dt:.2f}s")
    # save results
    with open('people_links.txt', 'w', encoding='utf-8') as f:
        # Décode les URLs pour afficher correctement les caractères accentués
        decoded_people = [unquote(link) for link in people]
        f.write('\n'.join(decoded_people))
    print('Saved people_links.txt')
