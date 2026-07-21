import math
import parser


"""
Program entry point
"""
def main() -> None:
    # 1. Parse
    args = parser.parse_args()
    print(vars(args))

    #2. Compute threshold
    """
    threshold = compute_threshold(
        capital=args.capital,
        labor=args.labor,
    )
    """

    #3. Compute equations for the threshold


    #4. Plot

    #print(f"Automation threshold: {threshold}")


if __name__ == "__main__":
    main()