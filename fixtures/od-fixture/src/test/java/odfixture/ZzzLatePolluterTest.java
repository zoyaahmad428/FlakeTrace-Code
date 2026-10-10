package odfixture;

import org.junit.Test;

/**
 * F4 polluter (ADR-008): class name sorts alphabetically late, so this always runs after
 * {@link AlwaysEarlyVictimTest} in this project's alphabetical discovery order. Sets
 * {@link LateFlag#isSet} and never restores it, but never gets the chance to run before the
 * victim without reordering the suite.
 */
public class ZzzLatePolluterTest {
    @Test
    public void setLateFlag() {
        LateFlag.isSet = true;
    }
}
