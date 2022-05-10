from argparse import ArgumentParser

import crwlr


def main():
    kwargs = dict()
    parser = ArgumentParser()
    parser.add_argument('-c', '--categories', help='file containing categories, one per line', default='categories.txt')
    args = parser.parse_args()
    categories = args.categories
    args = tuple()
    crwlr.start(categories, *args, **kwargs)



if __name__ == '__main__':
    main()
