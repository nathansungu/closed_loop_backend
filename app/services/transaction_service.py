from decimal import Decimal


def _get_participant_id(p):
    if hasattr(p, "participant_id"):
        return p.participant_id
    if hasattr(p, "id"):
        return p.id
    if isinstance(p, dict):
        return p.get("participant_id") or p.get("id")
    return getattr(p, "participant_id", getattr(p, "id", None))


def calculate_outgoing_transactions(
    cycle_participants,
    outgoing_cycle,
):
    """
    Calculate all money movements in the outgoing round.

    Each participant has their own initial_amount.

    The first participant starts with their recorded
    initial amount.

    Every participant after the first receives the
    circulating amount, adds their own initial amount,
    and sends the new total to the next participant.

    Example:

        1 = 100
        3 = 80
        5 = 100
        2 = 150
        4 = 120

        1 → 3 = 100
        3 → 5 = 180
        5 → 2 = 280
        2 → 4 = 430
        4 → 1 = 550
    """

    if not outgoing_cycle:
        raise ValueError("Outgoing cycle cannot be empty.")

    if not cycle_participants:
        raise ValueError("Cycle must have participants.")

    # -----------------------------------------------------
    # Build participant map
    # -----------------------------------------------------

    participant_map = {
        _get_participant_id(participant): participant for participant in cycle_participants
    }

    # -----------------------------------------------------
    # Verify that every participant in the cycle is
    # registered.
    # -----------------------------------------------------

    for participant_id in outgoing_cycle:

        if participant_id not in participant_map:

            raise ValueError(f"Participant {participant_id} " f"is not registered in this cycle.")

    # -----------------------------------------------------
    # Starting participant
    # -----------------------------------------------------

    starter_id = outgoing_cycle[0]

    starter = participant_map[starter_id]

    current_amount = Decimal(str(starter.initial_amount))

    transactions = []

    # -----------------------------------------------------
    # Process outgoing cycle
    # -----------------------------------------------------

    for index in range(len(outgoing_cycle)):

        from_id = outgoing_cycle[index]

        to_id = outgoing_cycle[(index + 1) % len(outgoing_cycle)]

        amount_to_send = current_amount

        transactions.append(
            {
                "round": "outgoing",
                "from_participant_id": from_id,
                "to_participant_id": to_id,
                "amount": amount_to_send,
            }
        )

        # -------------------------------------------------
        # If this is NOT the final sender,
        # the receiver adds their own initial amount.
        # -------------------------------------------------

        if index < len(outgoing_cycle) - 1:

            receiver = participant_map[to_id]

            receiver_amount = Decimal(str(receiver.initial_amount))

            current_amount = amount_to_send + receiver_amount

    return transactions


def calculate_total_circulating_amount(
    transactions,
):
    """
    Return the final amount circulating at the
    end of the outgoing round.
    """

    if not transactions:
        return Decimal("0")

    return Decimal(str(transactions[-1]["amount"]))


def format_transaction(
    transaction,
):
    """
    Format a transaction for display.
    """

    return (
        f"{transaction['from_participant_id']}"
        f" → "
        f"{transaction['to_participant_id']}"
        f" : "
        f"{transaction['amount']:.2f}"
    )


def display_transactions(
    transactions,
    title="TRANSACTIONS",
):
    """
    Display transactions in a readable format.
    """

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

    if not transactions:

        print("No transactions.")

        return

    for transaction in transactions:

        print(format_transaction(transaction))

    total = calculate_total_circulating_amount(transactions)

    print("\n" + "-" * 60)

    print(f"Final circulating amount: " f"{total:.2f}")


def calculate_return_transactions(
    cycle_participants,
    outgoing_cycle,
    return_cycle,
    outgoing_transactions,
):
    """
    Calculate all money movements in the return round.

    IMPORTANT MODEL:

    The participant who STARTED the outgoing round
    is also the FINAL RECEIVER of the outgoing round.

    Therefore:

        outgoing_cycle[0]

    is the participant who holds the complete
    accumulated amount when the outgoing round ends.

    That participant MUST start the return round.

    During the return round:

    1. The return starter keeps their own initial amount.
    2. They send the remaining amount to the next participant.
    3. That participant keeps their own initial amount.
    4. They send the remaining amount forward.
    5. This continues until everyone has recovered
       their original initial amount.

    Example:

        Initial amounts:

        1 = 100
        2 = 100
        3 = 100
        4 = 100
        5 = 100

        Outgoing:

        1 → 2 : 100
        2 → 3 : 200
        3 → 4 : 300
        4 → 5 : 400
        5 → 1 : 500

        Participant 1 now holds 500.

        Return:

        1 → 3 : 400
        3 → 5 : 300
        5 → 2 : 200
        2 → 4 : 100

        Participant 4 receives 100.

        Everyone has recovered their original 100.

    NOTE:

    There is no need for a final transaction from the
    last participant because they simply retain the
    amount they receive.
    """

    # -----------------------------------------------------
    # Basic validation
    # -----------------------------------------------------

    if not outgoing_cycle:
        raise ValueError("Outgoing cycle cannot be empty.")

    if not return_cycle:
        raise ValueError("Return cycle cannot be empty.")

    if not cycle_participants:
        raise ValueError("Cycle must have participants.")

    if not outgoing_transactions:
        raise ValueError("Outgoing transactions cannot be empty.")

    # -----------------------------------------------------
    # Build participant map
    # -----------------------------------------------------

    participant_map = {
        _get_participant_id(participant): participant for participant in cycle_participants
    }

    # -----------------------------------------------------
    # Verify every participant exists
    # -----------------------------------------------------

    for participant_id in return_cycle:

        if participant_id not in participant_map:

            raise ValueError(f"Participant {participant_id} " f"is not registered in this cycle.")

    # =====================================================
    # IMPORTANT FIX
    # =====================================================
    #
    # The final outgoing receiver is NOT:
    #
    #     outgoing_cycle[-1]
    #
    # Because the cycle closes back to the first
    # participant.
    #
    # Example:
    #
    #     4 → 5 → 1 → 2 → 3 → 4
    #
    # The final transaction is:
    #
    #     3 → 4
    #
    # Therefore participant 4 holds the final amount.
    #
    # So the person who starts the return round is:
    #
    #     outgoing_cycle[0]
    #
    # =====================================================

    outgoing_final_receiver = outgoing_cycle[0]

    return_starter = return_cycle[0]

    if return_starter != outgoing_final_receiver:

        raise ValueError(
            "Return cycle must start with the "
            "final receiver of the outgoing cycle. "
            f"Expected {outgoing_final_receiver}, "
            f"got {return_starter}."
        )

    # -----------------------------------------------------
    # Get final circulating amount
    # -----------------------------------------------------

    current_amount = Decimal(str(outgoing_transactions[-1]["amount"]))

    transactions = []

    # -----------------------------------------------------
    # Process return cycle
    # -----------------------------------------------------
    #
    # Example:
    #
    # Return:
    #
    # 4 → 1 → 3 → 5 → 2 → 4
    #
    # Starting amount:
    #
    # 550
    #
    # 4 keeps 100 and sends 450
    #
    # 1 keeps 150 and sends 300
    #
    # 3 keeps 100 and sends 200
    #
    # 5 keeps 100 and sends 100
    #
    # 2 receives 100 and is settled.
    #
    # -----------------------------------------------------

    for index in range(len(return_cycle) - 1):

        from_id = return_cycle[index]

        to_id = return_cycle[index + 1]

        sender = participant_map[from_id]

        sender_initial_amount = Decimal(str(sender.initial_amount))

        # -------------------------------------------------
        # Sender keeps their own initial amount.
        # -------------------------------------------------

        amount_to_send = current_amount - sender_initial_amount

        if amount_to_send < 0:

            raise ValueError(
                f"Participant {from_id} cannot retain "
                f"{sender_initial_amount:.2f} because only "
                f"{current_amount:.2f} is available."
            )

        # -------------------------------------------------
        # Record transaction.
        #
        # We don't need to record a zero-value transaction.
        # -------------------------------------------------

        if amount_to_send > 0:

            transactions.append(
                {
                    "round": "return",
                    "from_participant_id": from_id,
                    "to_participant_id": to_id,
                    "amount": amount_to_send,
                }
            )

        # -------------------------------------------------
        # Receiver now holds the remaining amount.
        # -------------------------------------------------

        current_amount = amount_to_send

    # -----------------------------------------------------
    # Final participant
    # -----------------------------------------------------
    #
    # The final participant should receive exactly their
    # initial amount.
    #
    # This confirms the entire cycle has settled correctly.
    # -----------------------------------------------------

    final_participant_id = return_cycle[-1]

    final_participant = participant_map[final_participant_id]

    final_initial_amount = Decimal(str(final_participant.initial_amount))

    if current_amount != final_initial_amount:

        raise ValueError(
            "Return round does not settle correctly. "
            f"Participant {final_participant_id} "
            f"should receive "
            f"{final_initial_amount:.2f}, "
            f"but the remaining amount is "
            f"{current_amount:.2f}."
        )

    return transactions
