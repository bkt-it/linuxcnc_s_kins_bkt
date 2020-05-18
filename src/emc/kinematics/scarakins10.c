/*****************************************************************
* Description: scarakins.c
*   Kinematics for scara typed robots
*   Set the params using HAL to fit your robot
*
*   Derived from a work by Sagar Behere
*
* Author: Sagar Behere
* License: GPL Version 2
* System: Linux
*
* Copyright (c) 2003 All rights reserved.
*
* Last change:
*******************************************************************
*/

#include "rtapi.h"
#include "rtapi_math.h"
#include "rtapi_string.h"
#include "posemath.h"
#include "hal.h"
#include "kinematics.h"
#include "switchkins.h"

struct scara_data {
    hal_float_t *d1, *d2, *d3, *d4, *d5, *d6;
} *haldata = 0;

/* key dimensions

   joint[0] = Entire arm rotates around a vertical axis at its inner end
                which is attached to the earth.  A value of zero means the
                inner arm is pointing along the X axis.
   D1 = Vertical distance from the ground plane to the center of the inner
                arm.
   D2 = Horizontal distance between joint[0] axis and joint[1] axis, ie.
                the length of the inner arm.
   joint[1] = Outer arm rotates around a vertical axis at its inner end
                which is attached to the outer end of the inner arm.  A
                value of zero means the outer arm is parallel to the
                inner arm (and extending outward).
   D3 = Vertical distance from the center of the inner arm to the center
                of the outer arm.  May be positive or negative depending
                on the structure of the robot.
   joint[2] = End effector slides along a vertical axis at the outer end
                of the outer arm.  A value of zero means the end effector
                is at the same height as the center of the outer arm, and
                positive values mean downward movement.
   D4 = Horizontal distance between joint[1] axis and joint[2] axis, ie.
                the length of the outer arm
   joint[5] = End effector rotates around the same vertical axis that it
                slides along.  A value of zero means that the tooltip (if
                offset from the axis) is pointing in the same direction
                as the centerline of the outer arm.
   D5 = Vertical distance from the end effector to the tooltip.  Positive
                means the tooltip is lower than the end effector, and is
                the normal case.
   D6 = Horizontal distance from the centerline of the end effector (and
                the joints 2 and 3 axis) and the tooltip.  Zero means the
                tooltip is on the centerline.  Non-zero values should be
                positive, if negative they introduce a 180 degree offset
                on the value of joint[3].
*/

#define D1 (*(haldata->d1))
#define D2 (*(haldata->d2))
#define D3 (*(haldata->d3))
#define D4 (*(haldata->d4))
#define D5 (*(haldata->d5))
#define D6 (*(haldata->d6))

/* joint[0], joint[1], joint[5], joint[3] and joint[4] are in degrees and joint[2] is in length units */
int scaraKinematicsForward(const double * joint,
                      EmcPose * world,
                      const KINEMATICS_FORWARD_FLAGS * fflags,
                      KINEMATICS_INVERSE_FLAGS * iflags)
{
    double a0, a1, a3;
    double x, y, z, c;

/* convert joint angles to radians for sin() and cos() */

    a0 = joint[0] * ( PM_PI / 180 );
    a1 = joint[1] * ( PM_PI / 180 );
    a3 = joint[5] * ( PM_PI / 180 );
/* convert angles into world coords */

    a1 = a1 + a0;
    a3 = a3 + a1;

    x = D2*cos(a0) + D4*cos(a1) + D6*cos(a3);
    y = D2*sin(a0) + D4*sin(a1) + D6*sin(a3);
    z = D1 + D3 - joint[2] - D5;
    c = a3;

    *iflags = 0;
    if (joint[1] < 90)
        *iflags = 1;

    world->tran.x = x;
    world->tran.y = y;
    world->tran.z = z;
    world->c = c * 180 / PM_PI;

    world->a = joint[3];
    world->b = joint[4];

    return (0);
} //scaraKinematicsForward()

int scaraKinematicsInverse(const EmcPose * world,
                      double * joint,
                      const KINEMATICS_INVERSE_FLAGS * iflags,
                      KINEMATICS_FORWARD_FLAGS * fflags)
{
    double a3;
    double q0, q1;
    double xt, yt, rsq, cc;
    double x, y, z, c;

    x = world->tran.x;
    y = world->tran.y;
    z = world->tran.z;
    c = world->c;

    /* convert degrees to radians */
    a3 = c * ( PM_PI / 180 );

    /* center of end effector (correct for D6) */
    xt = x - D6*cos(a3);
    yt = y - D6*sin(a3);

    /* horizontal distance (squared) from end effector centerline
        to main column centerline */
    rsq = xt*xt + yt*yt;
    /* joint 1 angle needed to make arm length match sqrt(rsq) */
    cc = (rsq - D2*D2 - D4*D4) / (2*D2*D4);
    if(cc < -1) cc = -1;
    if(cc > 1) cc = 1;
    q1 = acos(cc);

    if (*iflags)
        q1 = -q1;

    /* angle to end effector */
    q0 = atan2(yt, xt);

    /* end effector coords in inner arm coord system */
    xt = D2 + D4*cos(q1);
    yt = D4*sin(q1);

    /* inner arm angle */
    q0 = q0 - atan2(yt, xt);

    /* q0 and q1 are still in radians. convert them to degrees */
    q0 = q0 * (180 / PM_PI);
    q1 = q1 * (180 / PM_PI);

    joint[0] = q0;
    joint[1] = q1;
    joint[2] = D1 + D3 - D5 - z;
    joint[5] = c - ( q0 + q1);
    joint[3] = world->a;
    joint[4] = world->b;

    *fflags = 0;

    return (0);
} // scaraKinematicsInverse()

#define DEFAULT_D1 0
#define DEFAULT_D2 650
#define DEFAULT_D3 2000
#define DEFAULT_D4 617
#define DEFAULT_D5 200
#define DEFAULT_D6 0

int scaraKinematicsSetup(const  int   comp_id,
                         const  char* coordinates,
                         kparms*      kp)
{
    int res=0;

    haldata = hal_malloc(sizeof(*haldata));
    if (!haldata) goto error;

    res += hal_pin_float_new("scarakins10.D1", HAL_IO, &(haldata->d1), comp_id);
    res += hal_pin_float_new("scarakins10.D2", HAL_IO, &(haldata->d2), comp_id);
    res += hal_pin_float_new("scarakins10.D3", HAL_IO, &(haldata->d3), comp_id);
    res += hal_pin_float_new("scarakins10.D4", HAL_IO, &(haldata->d4), comp_id);
    res += hal_pin_float_new("scarakins10.D5", HAL_IO, &(haldata->d5), comp_id);
    res += hal_pin_float_new("scarakins10.D6", HAL_IO, &(haldata->d6), comp_id);
    if (res) { goto error; }

    D1 = DEFAULT_D1;
    D2 = DEFAULT_D2;
    D3 = DEFAULT_D3;
    D4 = DEFAULT_D4;
    D5 = DEFAULT_D5;
    D6 = DEFAULT_D6;

    return 0;

error:
    return -1;
} // scaraKinematicsSetup()

int switchkinsSetup(kparms* kp,
                    KS* kset0, KS* kset1, KS* kset2,
                    KF* kfwd0, KF* kfwd1, KF* kfwd2,
                    KI* kinv0, KI* kinv1, KI* kinv2
                   )
{
    kp->kinsname    = "scarakins10"; // !!! must agree with filename
    kp->halprefix   = "scarakins10"; // hal pin names
    kp->required_coordinates = "xyzabc";
    kp->allow_duplicates     = 0;
    kp->max_joints = strlen(kp->required_coordinates);

    rtapi_print("\n!!! switchkins-type 0 is %s\n",kp->kinsname);
    *kset0 = scaraKinematicsSetup;
    *kfwd0 = scaraKinematicsForward;
    *kinv0 = scaraKinematicsInverse;

    *kset1 = identityKinematicsSetup;
    *kfwd1 = identityKinematicsForward;
    *kinv1 = identityKinematicsInverse;

    *kset2 = userkKinematicsSetup;
    *kfwd2 = userkKinematicsForward;
    *kinv2 = userkKinematicsInverse;

    return 0;
} // switchkinsSetup()