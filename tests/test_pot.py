from holdem.engine.pot import Pot, award_pots, build_pots


def test_single_pot_no_side_pots():
    pots = build_pots({0: 100, 1: 100, 2: 100}, folded=set())
    assert pots == [Pot(300, frozenset({0, 1, 2}))]


def test_folded_chips_stay_in_pot_but_not_eligible():
    pots = build_pots({0: 100, 1: 300, 2: 300}, folded={0})
    assert pots == [Pot(700, frozenset({1, 2}))]


def test_three_way_all_in_side_pots():
    # A all-in 100, B all-in 300, C covers with 500 (200 uncalled).
    pots = build_pots({0: 100, 1: 300, 2: 500}, folded=set())
    assert pots == [
        Pot(300, frozenset({0, 1, 2})),
        Pot(400, frozenset({1, 2})),
        Pot(200, frozenset({2})),  # uncalled excess returned
    ]


def test_side_pot_with_folded_player_in_middle_layer():
    # Seat 3 put in 200 then folded.
    pots = build_pots({0: 100, 1: 300, 2: 300, 3: 200}, folded={3})
    assert sum(p.amount for p in pots) == 900
    assert pots == [Pot(400, frozenset({0, 1, 2})), Pot(500, frozenset({1, 2}))]


def test_short_stack_wins_main_big_stack_wins_side():
    pots = build_pots({0: 100, 1: 300, 2: 300}, folded=set())
    scores = {0: 1, 1: 50, 2: 10}  # seat 0 best, then seat 2
    winnings, _ = award_pots(pots, scores, button=0, num_seats=3)
    assert winnings == {0: 300, 2: 400}


def test_split_pot_with_odd_chip_goes_left_of_button():
    pots = [Pot(301, frozenset({0, 2}))]
    winnings, awards = award_pots(pots, {0: 5, 2: 5}, button=1, num_seats=3)
    # Left of button 1 is seat 2, so seat 2 gets the odd chip.
    assert winnings == {2: 151, 0: 150}
    assert awards == [(301, frozenset({0, 2}))]


def test_uncontested_pot_needs_no_scores():
    pots = build_pots({0: 50, 1: 100}, folded={0})
    winnings, _ = award_pots(pots, {}, button=0, num_seats=2)
    assert winnings == {1: 150}
