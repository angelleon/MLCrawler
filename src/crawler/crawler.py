from argparse import ArgumentParser

import crwlr


def main():
    # TODO: add argument for logging level
    parser = ArgumentParser()
    parser.add_argument('-c', '--categories', help='file containing categories, one per line', default='categories.txt')
    parser.add_argument('-p', '--pages', help='number search of pages to fetch and analyze', type=int, default=10)
    parser.add_argument('-o', '--output-links', help='file to write the search results on', default='product_links.csv')
    parser.add_argument('-O', '--output-details', help='file to write the results on', default='product_info.json')
    parser.add_argument('-n', '--num-procs', help='Number of processes', type=int, default=5)
    parser.add_argument('-t', '--timeout-q', help='Timeout when fetching from queues, in seconds', type=float, default=0.01)
    args = parser.parse_args()
    categories = args.categories
    pages = args.pages
    output_links = args.output_links
    num_procs = args.num_procs
    q_timeout = args.timeout_q
    output_details = args.output_details
    print(repr(q_timeout))
    args = tuple()
    kwargs = dict()
    crwlr.start(categories, pages, num_procs, output_links, output_details, q_timeout, *args, **kwargs)



if __name__ == '__main__':
    main()
