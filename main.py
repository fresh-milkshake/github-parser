from typing import List
import bs4, grequests, click
import dataclasses, csv, os
import logging

from tqdm import tqdm

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Repo:
    name: str
    about: str
    stars: str
    watchers: str
    forks: str
    url: str
    readme: str
    languages: str
    last_commit_date: str


SCRIPT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
BASE_URL = 'https://github.com'
REPOSITORIES_URL = BASE_URL + '/user?tab=repositories'


def save_to_csv(repositories: List[Repo], path: str):
    logger.info(f'Saving to file {path} ...')
    with open(path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(Repo.__annotations__.keys())
        for repo in repositories:
            writer.writerow(repo.__dict__.values())
    logger.info(f'Written {len(repositories)} lines to file')


@click.command()
@click.argument('username', type=str, required=True)
@click.option('--path',
              '-p',
              type=str,
              default=None,
              help='Path to csv file where repositories will be saved')
@click.option('--verbose',
              '-v',
              is_flag=True,
              default=False,
              help='Verbose mode')
def main(username: str, path: str, verbose: bool):
    if verbose:
        logger.setLevel(logging.INFO)

    if path is None:
        logger.warning(
            'Path to csv file is not specified. Using script directory ...')
        path = os.path.join(SCRIPT_DIRECTORY, f'{username}.csv')

    logger.info(f'Getting repositories of {username} ...')
    response = grequests.get(REPOSITORIES_URL.replace(
        'user', username)).send().response
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    raw_repos_urls = soup.find_all('a', {'itemprop': 'name codeRepository'})
    if not raw_repos_urls:
        logger.error(f'User {username} does not exist, or has no repositories')
        return

    repos_urls = [
        BASE_URL + repository['href'] for repository in raw_repos_urls
    ]

    logger.info(
        f'Found {len(repos_urls)} repositories, waiting for responses ...')
    responses = grequests.map([grequests.get(url) for url in repos_urls])
    repositories = []
    for response in tqdm(responses, desc='Parsing repositories', unit='repo'):
        soup = bs4.BeautifulSoup(response.text, 'html.parser')

        url = response.url
        name = url.split('/')[-1]
        about_section = soup.select_one('div .BorderGrid-cell')
        about = (about_section.select_one('p')
                 or about_section.select_one('div')).text.strip()
        stars, watchers, forks = [
            item.text.strip() for item in about_section.select('strong')
        ]

        languages = []
        languages_section = soup.select(
            'div.Layout-sidebar div.BorderGrid-row')[-1]
        languages_section = languages_section.select('ul span')
        for idx in range(0, len(languages_section), 2):
            language = languages_section[idx].text
            if 'Other' in language:
                break
            languages.append(language)

        languages = ', '.join(languages)

        if lst := soup.find('relative-time'):
            last_commit_date = lst.text
        else:
            last_commit_date = None

        repositories.append(
            Repo(name, about, stars, watchers, forks, url, '', languages,
                 last_commit_date))

    save_to_csv(repositories, path)
    logger.info('Successfully finished!')


if __name__ == '__main__':
    main()