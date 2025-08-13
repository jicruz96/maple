import { collection, getDocs, query, where } from "firebase/firestore"
import { useCallback, useEffect, useMemo, useState } from "react"
import { useAuth } from "../auth"
import { firestore } from "../firebase"
import {
  BillItem,
  buildFollowableItemsCard,
  UsersCard,
  UserItem,
  FollowableItemsCard
} from "./FollowableItemsCard"
import { useBill } from "components/db"
import { formatBillId } from "components/formatting"
import { Internal } from "components/links"
import { FollowBillButton } from "components/shared/FollowButton"
import { useTranslation } from "next-i18next"

export const BillsCard: FollowableItemsCard<BillItem> =
  buildFollowableItemsCard<BillItem>({
    itemBuilder: props => {
      const { court, billId } = props
      const { loading, result: bill } = useBill(court, billId)
      return {
        loading,
        followButton: <FollowBillButton confirmUnfollow={true} {...props} />,
        content: (
          <>
            <Internal href={`/bills/${court}/${billId}`}>
              {formatBillId(billId)}
            </Internal>
            <div className="ms-3">
              <h6>{bill?.content.Title}</h6>
            </div>
          </>
        )
      }
    }
  })

export function FollowingTab({ className }: { className?: string }) {
  const { user } = useAuth()
  const uid = user?.uid
  const subscriptionRef = useMemo(
    () =>
      // returns new object only if uid changes
      uid
        ? collection(firestore, `/users/${uid}/activeTopicSubscriptions/`)
        : null,
    [uid]
  )

  const [billsFollowing, setBillsFollowing] = useState<BillItem[]>([])
  const [usersFollowing, setUsersFollowing] = useState<UserItem[]>([])

  const billsFollowingQuery = useCallback(async () => {
    if (!subscriptionRef) return // handle the case where subscriptionRef is null
    const billList: BillItem[] = []
    const q = query(
      subscriptionRef,
      where("uid", "==", `${uid}`),
      where("type", "==", "bill")
    )
    const querySnapshot = await getDocs(q)
    querySnapshot.forEach(doc => {
      // doc.data() is never undefined for query doc snapshots
      billList.push(doc.data().billLookup)
    })
    if (billsFollowing.length === 0 && billList.length != 0) {
      setBillsFollowing(billList)
    }
  }, [subscriptionRef, uid, billsFollowing])

  useEffect(() => {
    uid ? billsFollowingQuery() : null
  })

  const orgsFollowingQuery = useCallback(async () => {
    if (!subscriptionRef) return // handle the case where subscriptionRef is null
    const usersList: UserItem[] = []
    const q = query(
      subscriptionRef,
      where("uid", "==", `${uid}`),
      where("type", "==", "testimony")
    )
    const querySnapshot = await getDocs(q)
    querySnapshot.forEach(doc => {
      // doc.data() is never undefined for query doc snapshots
      usersList.push(doc.data().userLookup)
    })

    if (usersFollowing.length === 0 && usersList.length != 0) {
      setUsersFollowing(usersList)
    }
  }, [subscriptionRef, uid, usersFollowing])

  const fetchFollowedItems = useCallback(async () => {
    if (uid) {
      billsFollowingQuery()
      orgsFollowingQuery()
    }
  }, [uid, billsFollowingQuery, orgsFollowingQuery])

  useEffect(() => {
    fetchFollowedItems()
  }, [billsFollowing, usersFollowing, fetchFollowedItems])

  const { t } = useTranslation("editProfile")

  return (
    <>
      <BillsCard
        className={className}
        title={t("follow.bills")}
        items={billsFollowing.map(bill => ({
          ...bill,
          onUnfollow: async () => setBillsFollowing([])
        }))}
      />
      <UsersCard
        className={className}
        title={t("follow.orgs")}
        items={usersFollowing.map(user => ({
          ...user,
          onUnfollow: async () => setUsersFollowing([])
        }))}
      />
    </>
  )
}
