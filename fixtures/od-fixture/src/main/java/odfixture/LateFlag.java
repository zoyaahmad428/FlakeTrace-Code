package odfixture;

/** F4 fixture: a static field with a well-defined default that a test can pollute. */
public class LateFlag {
    public static boolean isSet = false;
}
