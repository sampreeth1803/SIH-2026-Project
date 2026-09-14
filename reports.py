def print_report(traffic_data, plate_results=None):
    vehicle_counts = traffic_data["vehicle_counts"]
    vehicle_counts = {
        "car": vehicle_counts.get("car", 0),
        "motorcycle": vehicle_counts.get("motorcycle", 0),
        "bus": vehicle_counts.get("bus", 0),
        "truck": vehicle_counts.get("truck", 0),
    }
    total_vehicles = sum(vehicle_counts.values())

    peak_occupancy = traffic_data["peak_occupancy"]
    average_occupancy = traffic_data["average_occupancy"]

    if peak_occupancy >= 0.35 or average_occupancy >= 0.20:
        traffic_level = "HIGH"
    elif peak_occupancy >= 0.20 or average_occupancy >= 0.10:
        traffic_level = "MEDIUM"
    else:
        traffic_level = "LOW"

    print("\nINTELLIGENT TRAFFIC MONITOR")
    print("=" * 32)
    print(f"Total unique vehicles: {total_vehicles}")
    print(f"Average road occupancy: {average_occupancy:.1%}")
    print(f"Peak road occupancy: {peak_occupancy:.1%}")
    print(f"Traffic level: {traffic_level}")
    print("\nVehicle breakdown:")
    for vehicle, count in vehicle_counts.items():
        print(f"  {vehicle}: {count}")

    if plate_results:
        print("\nANPR results:")
        for detection in plate_results:
            text, confidence = detection[1], detection[2]
            print(f"  {text} ({confidence:.2f})")
