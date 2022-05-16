from argparse import ArgumentParser

import crwlr


def main():
    parser = ArgumentParser()
    parser.add_argument('-c', '--categories', help='file containing categories, one per line', default='categories.txt')
    parser.add_argument('-p', '--pages', help='number search of pages to fetch and analyze', type=int, default=10)
    parser.add_argument('-o', '--output', help='file to write the results on', default='results.csv')
    parser.add_argument('-n', '--num-procs', help='Number of processes', type=int, default=5)
    parser.add_argument('-t', '--timeout-q', help='Timeout when fetching from queues, in seconds', type=float, default=0.01)
    parser.add_argument
    args = parser.parse_args()
    categories = args.categories
    pages = args.pages
    output = args.output
    num_procs = args.num_procs
    q_timeout = args.timeout_q
    print(repr(q_timeout))
    args = tuple()
    kwargs = dict()
    crwlr.start(categories, pages, num_procs, output, q_timeout, *args, **kwargs)



if __name__ == '__main__':
    main()
